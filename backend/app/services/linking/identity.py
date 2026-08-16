from __future__ import annotations

from rapidfuzz import fuzz

from app.db.models import Patient
from app.services.linking.patients import STRONG_FUZZY, WEAK_FUZZY
from app.services.normalization.names import normalize_person_name
from app.services.normalization.phones import normalize_phone


def target_identity_compatible(
    extracted_name: str | None,
    extracted_phone: str | None,
    extracted_dob: str | None,
    target: Patient,
) -> tuple[bool, str]:
    """Decide whether extracted identity may be filed on the selected patient.

    Name and phone identify the person. Hospital IDs are metadata and are
    not used as a match key.
    """
    extracted_norm = normalize_person_name(extracted_name)
    target_norm = target.normalized_name or normalize_person_name(target.canonical_name)
    extracted_phone_n = normalize_phone(extracted_phone)
    target_phone = target.normalized_phone or normalize_phone(target.phone)

    if not extracted_norm and not extracted_phone_n:
        return False, "document has no patient name or phone, so it cannot be filed on a chart"

    if extracted_phone_n and target_phone and extracted_phone_n != target_phone:
        return False, f"document phone does not match the chart phone"

    if extracted_dob and target.date_of_birth and extracted_dob != target.date_of_birth:
        return False, f"document date of birth {extracted_dob} does not match {target.date_of_birth}"

    if extracted_phone_n and target_phone and extracted_phone_n == target_phone:
        if extracted_norm and target_norm:
            score = float(fuzz.token_sort_ratio(extracted_norm, target_norm))
            if score < WEAK_FUZZY:
                return False, (
                    f"document name {extracted_name!r} conflicts with {target.canonical_name!r}"
                )
        return True, "phone match"

    if not extracted_norm or not target_norm:
        return False, "a matching patient name is required when phone is missing"

    score = float(fuzz.token_sort_ratio(extracted_norm, target_norm))
    last_score = float(fuzz.ratio(extracted_norm.split()[-1], target_norm.split()[-1]))
    if score >= STRONG_FUZZY or (score >= WEAK_FUZZY and last_score >= 80):
        return True, f"fuzzy name match {score:.0f}"
    return False, (
        f"document name {extracted_name!r} does not match {target.canonical_name!r} "
        f"(name score {score:.0f})"
    )


def identity_warnings(
    extracted_name: str | None,
    extracted_phone: str | None,
    extracted_dob: str | None,
    target: Patient,
) -> list[str]:
    """Warnings for the confirmation step. Missing or inexact identity is not silent."""
    warnings: list[str] = []
    extracted_norm = normalize_person_name(extracted_name)
    target_norm = target.normalized_name or normalize_person_name(target.canonical_name)
    extracted_phone_n = normalize_phone(extracted_phone)
    target_phone = target.normalized_phone or normalize_phone(target.phone)

    if not extracted_norm:
        warnings.append("Could not extract a patient name from the document.")
    if not extracted_phone_n:
        warnings.append("Could not extract a phone number from the document.")

    if extracted_norm and target_norm and extracted_norm != target_norm:
        score = float(fuzz.token_sort_ratio(extracted_norm, target_norm))
        if score >= STRONG_FUZZY:
            warnings.append(
                f"Extracted name {extracted_name!r} is slightly different from "
                f"the selected chart name {target.canonical_name!r}."
            )
        else:
            warnings.append(
                f"Extracted name {extracted_name!r} does not match "
                f"the selected chart name {target.canonical_name!r} (name score {score:.0f})."
            )
    elif extracted_norm and not target_norm:
        warnings.append(
            f"The selected chart has no name yet. The document name is {extracted_name!r}."
        )

    if extracted_phone_n and target_phone and extracted_phone_n != target_phone:
        warnings.append("Extracted phone number differs from the chart phone number.")
    elif extracted_phone_n and not target_phone:
        warnings.append(f"The selected chart has no phone yet. The document phone is {extracted_phone}.")

    if extracted_dob and target.date_of_birth and extracted_dob != target.date_of_birth:
        warnings.append(
            f"Extracted date of birth {extracted_dob} differs from {target.date_of_birth}."
        )
    return warnings
