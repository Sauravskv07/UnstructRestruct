from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Document, LabResult, Medication
from app.db.session import get_db
from app.services import access as access_service
from app.services.document_status import HIDDEN_FROM_CHART

router = APIRouter(prefix="/query", tags=["query"])


def _allowed(
    db: Session,
    x_app_role: str | None,
    x_patient_id: str | None,
    x_clinician_id: str | None,
) -> list[str]:
    return access_service.visible_patient_ids(db, x_app_role, x_patient_id, x_clinician_id)


@router.get("/lab-results")
def query_lab_results(
    patient_id: str | None = None,
    test: str | None = None,
    validation_status: str | None = None,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    allowed = _allowed(db, x_app_role, x_patient_id, x_clinician_id)
    if not allowed:
        return []
    if patient_id and patient_id not in allowed:
        raise HTTPException(403, "no access to this patient")
    query = db.query(LabResult).join(Document).filter(
        LabResult.patient_id.in_(allowed),
        Document.status.notin_(HIDDEN_FROM_CHART),
    )
    if patient_id:
        query = query.filter(LabResult.patient_id == patient_id)
    if test:
        query = query.filter(LabResult.canonical_name == test.lower())
    if validation_status:
        query = query.filter(LabResult.validation_status == validation_status)
    rows = query.order_by(LabResult.test_date.asc()).all()
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "patient_id": r.patient_id,
            "test_date": r.test_date,
            "raw_name": r.raw_name,
            "canonical_name": r.canonical_name,
            "value": r.value,
            "unit": r.unit,
            "validation_status": r.validation_status,
        }
        for r in rows
    ]


@router.get("/medications")
def query_medications(
    patient_id: str | None = None,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    allowed = _allowed(db, x_app_role, x_patient_id, x_clinician_id)
    if not allowed:
        return []
    if patient_id and patient_id not in allowed:
        raise HTTPException(403, "no access to this patient")
    query = db.query(Medication).join(Document).filter(
        Medication.patient_id.in_(allowed),
        Document.status.notin_(HIDDEN_FROM_CHART),
    )
    if patient_id:
        query = query.filter(Medication.patient_id == patient_id)
    rows = query.order_by(Medication.prescribed_date.asc()).all()
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "patient_id": r.patient_id,
            "prescribed_date": r.prescribed_date,
            "raw_name": r.raw_name,
            "canonical_name": r.canonical_name,
            "strength": r.strength,
            "frequency": r.frequency,
            "validation_status": r.validation_status,
        }
        for r in rows
    ]


@router.get("/needs-review")
def needs_review(
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    allowed = _allowed(db, x_app_role, x_patient_id, x_clinician_id)
    if not allowed:
        return []
    docs = (
        db.query(Document)
        .filter(
            Document.needs_review.is_(True),
            Document.patient_id.in_(allowed),
            Document.status.notin_(HIDDEN_FROM_CHART),
        )
        .all()
    )
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "document_type": d.document_type,
            "patient_id": d.patient_id,
        }
        for d in docs
    ]
