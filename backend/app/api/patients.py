import re

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from rapidfuzz import fuzz
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import DiagnosticReport, Document, LabResult, Medication, Patient
from app.db.session import get_db
from app.services import access as access_service
from app.services.document_status import HIDDEN_FROM_CHART
from app.services.normalization.names import (
    normalize_medication_name,
    normalize_study_name,
    normalize_test_name,
)
from app.services.timeline import cluster_timeline
from app.services.vocab import DX, LAB, MED, chart_term_ids, search as search_vocab

router = APIRouter(prefix="/patients", tags=["patients"])


def _require_view(
    db: Session,
    patient_id: str,
    x_app_role: str | None,
    x_patient_id: str | None,
    x_clinician_id: str | None,
) -> None:
    if not access_service.can_view_patient(db, patient_id, x_app_role, x_patient_id, x_clinician_id):
        raise HTTPException(403, "no access to this patient")


@router.get("")
def list_patients(
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    query = db.query(Patient)
    if x_app_role == "clinician":
        if not x_clinician_id:
            return []
        ids = access_service.clinician_patient_ids(db, x_clinician_id)
        if not ids:
            return []
        query = query.filter(Patient.id.in_(ids))
    elif x_app_role == "patient":
        if not x_patient_id:
            return []
        query = query.filter(Patient.id == x_patient_id)
    else:
        return []
    patients = query.order_by(Patient.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "canonical_name": p.canonical_name,
            "phone": p.phone,
            "username": p.username,
            "external_patient_id": p.external_patient_id,
            "date_of_birth": p.date_of_birth,
            "needs_review": p.needs_review,
            "document_count": len([d for d in p.documents if d.status not in HIDDEN_FROM_CHART]),
        }
        for p in patients
    ]


@router.get("/{patient_id}")
def get_patient(
    patient_id: str,
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "patient not found")
    _require_view(db, patient_id, x_app_role, x_patient_id, x_clinician_id)
    docs = sorted(
        [d for d in patient.documents if d.status not in HIDDEN_FROM_CHART],
        key=lambda d: (d.document_date or "", d.created_at.isoformat() if d.created_at else ""),
    )
    if date_from or date_to:
        docs = [d for d in docs if d.document_date and _in_range(d.document_date, date_from, date_to)]
    timeline = []
    for doc in docs:
        item = {
            "document_id": doc.id,
            "filename": doc.filename,
            "document_type": doc.document_type,
            "date": doc.document_date,
            "status": doc.status,
            "needs_review": doc.needs_review,
        }
        if doc.document_type == "lab_report":
            item["summary"] = [
                f"{r.canonical_name or r.raw_name}: {r.value} {r.unit or ''}".strip()
                for r in doc.lab_results
            ]
        elif doc.document_type == "prescription":
            item["summary"] = [_medication_line(m) for m in doc.medications]
        elif doc.document_type == "diagnostic_report" and doc.diagnostic_report:
            item["summary"] = [doc.diagnostic_report.study or "diagnostic report"]
            if doc.diagnostic_report.impression:
                item["summary"].append(doc.diagnostic_report.impression)
        timeline.append(item)
    return {
        "id": patient.id,
        "canonical_name": patient.canonical_name,
        "phone": patient.phone,
        "username": patient.username,
        "external_patient_id": patient.external_patient_id,
        "date_of_birth": patient.date_of_birth,
        "needs_review": patient.needs_review,
        "timeline": timeline,
        "clusters": cluster_timeline(timeline),
    }


@router.get("/{patient_id}/catalog")
def patient_catalog(
    patient_id: str,
    kind: str | None = None,
    q: str = "",
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "patient not found")
    _require_view(db, patient_id, x_app_role, x_patient_id, x_clinician_id)
    chart = _chart_term_ids(db, patient_id)
    if kind:
        if kind not in chart:
            raise HTTPException(400, "kind must be lab_test, medication, or diagnostic")
        return [_hit(item) for item in search_vocab(db, kind, q, chart[kind])]
    return {
        "lab_tests": [_hit(item) for item in search_vocab(db, LAB, q, chart[LAB])],
        "medications": [_hit(item) for item in search_vocab(db, MED, q, chart[MED])],
        "diagnostics": [_hit(item) for item in search_vocab(db, DX, q, chart[DX])],
    }


@router.get("/{patient_id}/lab-results")
def patient_lab_results(
    patient_id: str,
    test: str | None = None,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    if not db.get(Patient, patient_id):
        raise HTTPException(404, "patient not found")
    _require_view(db, patient_id, x_app_role, x_patient_id, x_clinician_id)
    query = (
        db.query(LabResult)
        .join(Document)
        .filter(
            Document.status.notin_(HIDDEN_FROM_CHART),
            or_(LabResult.patient_id == patient_id, Document.patient_id == patient_id),
        )
    )
    if test:
        wanted = (normalize_test_name(test) or test).lower()
        rows = [
            row
            for row in query.order_by(LabResult.test_date.asc()).all()
            if (row.canonical_name or "").lower() == wanted
            or (normalize_test_name(row.raw_name) or "") == wanted
        ]
        return [_lab(row) for row in rows]
    rows = query.order_by(LabResult.test_date.asc()).all()
    return [_lab(row) for row in rows]


@router.get("/{patient_id}/medications")
def patient_medications(
    patient_id: str,
    name: str | None = None,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    if not db.get(Patient, patient_id):
        raise HTTPException(404, "patient not found")
    _require_view(db, patient_id, x_app_role, x_patient_id, x_clinician_id)
    rows = (
        db.query(Medication)
        .join(Document)
        .filter(
            Document.status.notin_(HIDDEN_FROM_CHART),
            or_(Medication.patient_id == patient_id, Document.patient_id == patient_id),
        )
        .order_by(Medication.prescribed_date.asc())
    )
    fetched = rows.all()
    if name:
        wanted = (normalize_medication_name(name) or name).lower()
        fetched = [
            row
            for row in fetched
            if (row.canonical_name or "").lower() == wanted
            or (normalize_medication_name(row.raw_name) or "") == wanted
        ]
    return [{**_med(row), "line": _medication_line(row), "filename": row.document.filename} for row in fetched]


@router.get("/{patient_id}/diagnostics")
def patient_diagnostics(
    patient_id: str,
    study: str | None = None,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    if not db.get(Patient, patient_id):
        raise HTTPException(404, "patient not found")
    _require_view(db, patient_id, x_app_role, x_patient_id, x_clinician_id)
    query = (
        db.query(DiagnosticReport)
        .join(Document)
        .filter(
            Document.status.notin_(HIDDEN_FROM_CHART),
            or_(DiagnosticReport.patient_id == patient_id, Document.patient_id == patient_id),
        )
        .order_by(DiagnosticReport.report_date.asc())
    )
    fetched = query.all()
    if study:
        wanted = (normalize_study_name(study) or study).lower()
        fetched = [
            row
            for row in fetched
            if (row.canonical_study or "").lower() == wanted
            or (normalize_study_name(row.study) or "") == wanted
        ]
    return [
        {
            "id": row.id,
            "document_id": row.document_id,
            "filename": row.document.filename,
            "report_date": row.report_date,
            "study": row.study,
            "canonical_study": row.canonical_study,
            "impression": row.impression,
            "findings": row.findings,
        }
        for row in fetched
    ]


def _visible_rows(db: Session, model, patient_id: str):
    return (
        db.query(model)
        .join(Document)
        .filter(
            Document.status.notin_(HIDDEN_FROM_CHART),
            or_(model.patient_id == patient_id, Document.patient_id == patient_id),
        )
        .all()
    )


def _chart_term_ids(db: Session, patient_id: str) -> dict[str, set[str]]:
    labs = _visible_rows(db, LabResult, patient_id)
    meds = _visible_rows(db, Medication, patient_id)
    studies = _visible_rows(db, DiagnosticReport, patient_id)
    lab_tokens = {value for row in labs for value in (row.canonical_name, row.raw_name, normalize_test_name(row.raw_name))}
    med_tokens = {value for row in meds for value in (row.canonical_name, row.raw_name, normalize_medication_name(row.raw_name))}
    dx_tokens = {
        value
        for row in studies
        for value in (row.canonical_study, row.study, normalize_study_name(row.study), normalize_study_name(row.canonical_study))
    }
    return {
        LAB: chart_term_ids(db, LAB, lab_tokens),
        MED: chart_term_ids(db, MED, med_tokens),
        DX: chart_term_ids(db, DX, dx_tokens),
    }


def _in_range(value: str, date_from: str | None, date_to: str | None) -> bool:
    if date_from and value < date_from:
        return False
    if date_to and value > date_to:
        return False
    return True


def _hit(item) -> dict:
    return {"id": item.id, "label": item.label, "in_chart": item.in_chart, "score": item.score}


def _lab(row: LabResult) -> dict:
    return {
        "id": row.id,
        "document_id": row.document_id,
        "filename": row.document.filename if row.document else None,
        "test_date": row.test_date,
        "raw_name": row.raw_name,
        "canonical_name": row.canonical_name,
        "raw_value": row.raw_value,
        "value": row.value,
        "unit": row.unit,
        "reference_low": row.reference_low,
        "reference_high": row.reference_high,
        "abnormal_flag": row.abnormal_flag,
        "confidence": row.confidence,
        "validation_status": row.validation_status,
        "provenance": row.provenance_json,
    }


def _norm_med_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _extra_instruction(structured: str, name: str, instructions: str | None) -> str | None:
    if not instructions:
        return None
    text = re.sub(r"^\s*\d+[.)]\s*", "", instructions).strip()
    if not text:
        return None
    known = set(_norm_med_text(structured).split())
    name_tokens = set(_norm_med_text(name).split())
    leftover: list[str] = []
    stop = {"for", "of", "the", "a", "an", "with", "and", "to", "per"}
    for token in _norm_med_text(text).split():
        if token.isdigit() or token in known or token in stop:
            continue
        if any(fuzz.ratio(token, part) >= 80 for part in name_tokens):
            continue
        leftover.append(token)
    if not leftover:
        return None
    return " ".join(leftover)


def _medication_line(row: Medication) -> str:
    name = row.canonical_name or row.raw_name or "medication"
    details = [
        part
        for part in (row.strength, row.dose, row.frequency, row.route, row.duration, row.quantity)
        if part
    ]
    line = " · ".join([name, *details])
    extra = _extra_instruction(line, name, row.instructions)
    if extra:
        return f"{line} — {extra}"
    return line


def _med(row: Medication) -> dict:
    return {
        "id": row.id,
        "document_id": row.document_id,
        "prescribed_date": row.prescribed_date,
        "raw_name": row.raw_name,
        "canonical_name": row.canonical_name,
        "strength": row.strength,
        "dose": row.dose,
        "route": row.route,
        "frequency": row.frequency,
        "duration": row.duration,
        "instructions": row.instructions,
        "validation_status": row.validation_status,
        "provenance": row.provenance_json,
    }
