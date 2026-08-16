from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.db import models
from app.services.normalization.names import normalize_person_name
from app.services.normalization.phones import normalize_phone


STRONG_FUZZY = 92
WEAK_FUZZY = 70


@dataclass
class LinkResult:
    patient_id: str | None
    match_method: str
    match_reason: str
    confidence: float
    needs_review: bool
    candidate_patient_ids: list[str]


def link_patient(db: Session, canonical) -> LinkResult:
    patient = canonical.patient
    name = patient.name
    hospital_id = patient.patient_id
    dob = patient.date_of_birth
    phone = patient.phone
    norm_name = normalize_person_name(name)
    norm_phone = normalize_phone(phone)

    if norm_name and norm_phone:
        matches = (
            db.query(models.Patient)
            .filter(models.Patient.normalized_name == norm_name, models.Patient.normalized_phone == norm_phone)
            .all()
        )
        if len(matches) == 1:
            match = matches[0]
            _maybe_fill(match, name, norm_name, dob, hospital_id, phone, norm_phone)
            return LinkResult(match.id, "name_and_phone", "normalized name and phone match", 0.98, False, [match.id])
        if len(matches) > 1:
            created = _create(db, name, norm_name, hospital_id, dob, True, phone, norm_phone)
            return LinkResult(
                created.id,
                "ambiguous_name_and_phone",
                "multiple patients share this name and phone; not merged",
                0.3,
                True,
                [p.id for p in matches] + [created.id],
            )

    if norm_phone:
        by_phone = db.query(models.Patient).filter(models.Patient.normalized_phone == norm_phone).all()
        if len(by_phone) == 1:
            match = by_phone[0]
            if norm_name and match.normalized_name:
                score = float(fuzz.token_sort_ratio(norm_name, match.normalized_name))
                if score < WEAK_FUZZY:
                    created = _create(db, name, norm_name, hospital_id, dob, True, phone, norm_phone)
                    return LinkResult(
                        created.id,
                        "phone_name_conflict",
                        "same phone but conflicting name; not merged",
                        0.35,
                        True,
                        [match.id, created.id],
                    )
            _maybe_fill(match, name, norm_name, dob, hospital_id, phone, norm_phone)
            return LinkResult(match.id, "phone", "phone number match", 0.9, False, [match.id])

    if norm_name and dob:
        matches = (
            db.query(models.Patient)
            .filter(models.Patient.normalized_name == norm_name, models.Patient.date_of_birth == dob)
            .all()
        )
        if len(matches) == 1:
            match = matches[0]
            _maybe_fill(match, name, norm_name, dob, hospital_id, phone, norm_phone)
            return LinkResult(match.id, "name_and_dob", "normalized name and date of birth match", 0.95, False, [match.id])

    candidates = db.query(models.Patient).all()
    scored: list[tuple[float, models.Patient]] = []
    for cand in candidates:
        score = 0.0
        if norm_name and cand.normalized_name:
            score = float(fuzz.token_sort_ratio(norm_name, cand.normalized_name))
        if dob and cand.date_of_birth and dob != cand.date_of_birth:
            score *= 0.4
        if norm_phone and cand.normalized_phone and norm_phone != cand.normalized_phone:
            score *= 0.2
        scored.append((score, cand))
    scored.sort(key=lambda item: item[0], reverse=True)
    strong = [(s, p) for s, p in scored if s >= STRONG_FUZZY]

    if len(strong) == 1 and dob and strong[0][1].date_of_birth and dob != strong[0][1].date_of_birth:
        created = _create(db, name, norm_name, hospital_id, dob, True, phone, norm_phone)
        return LinkResult(
            created.id,
            "name_similar_dob_mismatch",
            "similar name but different DOB; created separate patient",
            0.35,
            True,
            [strong[0][1].id, created.id],
        )

    if len(strong) > 1:
        created = _create(db, name, norm_name, hospital_id, dob, True, phone, norm_phone)
        ids = [p.id for _, p in strong] + [created.id]
        return LinkResult(
            created.id,
            "ambiguous_fuzzy_name",
            "multiple similar patients; not merged",
            0.3,
            True,
            ids,
        )

    if len(strong) == 1 and not dob and not strong[0][1].date_of_birth and not hospital_id and not norm_phone:
        created = _create(db, name, norm_name, hospital_id, dob, True, phone, norm_phone)
        return LinkResult(
            created.id,
            "ambiguous_name_only",
            "name is similar but identifiers are insufficient to merge",
            0.45,
            True,
            [strong[0][1].id, created.id],
        )

    if len(strong) == 1 and (dob or norm_phone or (norm_name and strong[0][1].normalized_name == norm_name)):
        match = strong[0][1]
        if norm_name and match.normalized_name == norm_name and (dob is None or match.date_of_birth is None or match.date_of_birth == dob):
            if dob and match.date_of_birth and dob != match.date_of_birth:
                created = _create(db, name, norm_name, hospital_id, dob, True, phone, norm_phone)
                return LinkResult(created.id, "dob_mismatch", "same name, different DOB", 0.3, True, [match.id, created.id])
            _maybe_fill(match, name, norm_name, dob, hospital_id, phone, norm_phone)
            return LinkResult(match.id, "exact_normalized_name", "unique exact normalized name", 0.8, False, [match.id])

    weak = [(s, p) for s, p in scored if s >= WEAK_FUZZY]
    if weak:
        created = _create(db, name, norm_name, hospital_id, dob, True, phone, norm_phone)
        ids = [p.id for _, p in weak] + [created.id]
        return LinkResult(
            created.id,
            "ambiguous_partial_name",
            "partial/similar name without enough identifiers to merge",
            0.4,
            True,
            ids,
        )

    created = _create(db, name, norm_name, hospital_id, dob, False, phone, norm_phone)
    return LinkResult(created.id, "new_patient", "no deterministic match; created patient", 0.7, False, [created.id])


def _create(
    db: Session,
    name: str | None,
    norm_name: str | None,
    external_id: str | None,
    dob: str | None,
    needs_review: bool,
    phone: str | None = None,
    norm_phone: str | None = None,
) -> models.Patient:
    patient = models.Patient(
        canonical_name=name,
        normalized_name=norm_name,
        external_patient_id=external_id,
        date_of_birth=dob,
        phone=phone,
        normalized_phone=norm_phone,
        needs_review=needs_review,
    )
    db.add(patient)
    db.flush()
    return patient


def _maybe_fill(
    patient: models.Patient,
    name: str | None,
    norm_name: str | None,
    dob: str | None,
    external_id: str | None = None,
    phone: str | None = None,
    norm_phone: str | None = None,
) -> None:
    if name and not patient.canonical_name:
        patient.canonical_name = name
    if norm_name and not patient.normalized_name:
        patient.normalized_name = norm_name
    if dob and not patient.date_of_birth:
        patient.date_of_birth = dob
    if external_id and not patient.external_patient_id:
        patient.external_patient_id = external_id
    if phone and not patient.phone:
        patient.phone = phone
    if norm_phone and not patient.normalized_phone:
        patient.normalized_phone = norm_phone
