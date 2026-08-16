from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Clinician, Patient
from app.db.session import get_db
from app.services import access as access_service
from app.services.access import _aware, hash_password, verify_password
from app.services.document_status import HIDDEN_FROM_CHART
from app.services.normalization.names import normalize_person_name
from app.services.normalization.phones import normalize_phone

router = APIRouter(tags=["access"])


class PatientLoginBody(BaseModel):
    password: str
    username: str | None = None
    patient_id: str | None = None
    name: str | None = None
    phone: str | None = None


class ClinicianLoginBody(BaseModel):
    clinician_id: str
    password: str


class AddPatientBody(BaseModel):
    patient_id: str
    code: str


def _serialize_code(row) -> dict | None:
    if row is None:
        return None
    now = datetime.now(timezone.utc)
    return {
        "code": row.code,
        "created_at": row.created_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "revoked": row.revoked_at is not None,
        "expired": _aware(row.expires_at) <= now or row.revoked_at is not None,
    }


def _find_patient(db: Session, handle: str) -> Patient | None:
    pid = handle.strip()
    patient = (
        db.query(Patient)
        .filter(func.lower(Patient.username) == pid.lower())
        .first()
    )
    if patient:
        return patient
    patient = (
        db.query(Patient)
        .filter(func.lower(Patient.external_patient_id) == pid.lower())
        .first()
    )
    if patient:
        return patient
    return db.get(Patient, pid)


def _find_clinician(db: Session, clinician_id: str) -> Clinician | None:
    cid = clinician_id.strip()
    clinician = (
        db.query(Clinician)
        .filter(func.lower(Clinician.external_id) == cid.lower())
        .first()
    )
    if clinician:
        return clinician
    return db.get(Clinician, cid)


@router.post("/auth/patient")
def patient_login(body: PatientLoginBody, db: Session = Depends(get_db)):
    handle = (body.username or body.patient_id or "").strip()
    if not handle:
        raise HTTPException(400, "username required")
    if not body.password:
        raise HTTPException(400, "password required")

    patient = _find_patient(db, handle)
    if patient is None:
        phone = body.phone.strip() if body.phone else None
        name = body.name.strip() if body.name else None
        patient = Patient(
            username=handle,
            password_hash=hash_password(body.password),
            canonical_name=name,
            normalized_name=normalize_person_name(name),
            phone=phone,
            normalized_phone=normalize_phone(phone),
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
    elif patient.password_hash:
        if not verify_password(body.password, patient.password_hash):
            raise HTTPException(401, "incorrect password")
    elif body.password != settings.demo_patient_password:
        raise HTTPException(401, "incorrect password")
    if not patient.username:
        patient.username = handle
        db.commit()

    return {
        "role": "patient",
        "patient_id": patient.id,
        "username": patient.username,
        "external_patient_id": patient.external_patient_id,
        "canonical_name": patient.canonical_name,
        "phone": patient.phone,
    }


@router.post("/auth/clinician")
def clinician_login(body: ClinicianLoginBody, db: Session = Depends(get_db)):
    cid = body.clinician_id.strip()
    if not cid:
        raise HTTPException(400, "clinician ID required")
    if not body.password:
        raise HTTPException(400, "password required")

    clinician = _find_clinician(db, cid)
    if clinician is None:
        clinician = Clinician(
            external_id=cid,
            name=f"Clinician {cid}",
            password_hash=hash_password(body.password),
        )
        db.add(clinician)
        db.commit()
        db.refresh(clinician)
    elif clinician.password_hash:
        if not verify_password(body.password, clinician.password_hash):
            raise HTTPException(401, "incorrect password")
    elif body.password != settings.demo_patient_password:
        raise HTTPException(401, "incorrect password")

    return {
        "role": "clinician",
        "clinician_id": clinician.id,
        "external_id": clinician.external_id,
        "name": clinician.name,
    }


@router.get("/me/share-code")
def get_share_code(
    x_patient_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_patient_id:
        raise HTTPException(401, "patient session required")
    if not db.get(Patient, x_patient_id):
        raise HTTPException(404, "patient not found")
    return {"code": _serialize_code(access_service.active_code(db, x_patient_id))}


@router.post("/me/share-code")
def create_share_code(
    x_patient_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_patient_id:
        raise HTTPException(401, "patient session required")
    if not db.get(Patient, x_patient_id):
        raise HTTPException(404, "patient not found")
    row = access_service.generate_code(db, x_patient_id)
    db.commit()
    return {"code": _serialize_code(row)}


@router.post("/me/share-code/revoke")
def revoke_share_code(
    x_patient_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_patient_id:
        raise HTTPException(401, "patient session required")
    access_service.revoke_active_code(db, x_patient_id)
    db.commit()
    return {"ok": True}


@router.post("/clinician/patients")
def add_patient(
    body: AddPatientBody,
    db: Session = Depends(get_db),
    x_clinician_id: str | None = Header(default=None),
):
    if not x_clinician_id:
        raise HTTPException(401, "clinician session required")
    if not db.get(Clinician, x_clinician_id):
        raise HTTPException(401, "unknown clinician")
    patient = _find_patient(db, body.patient_id)
    if patient is None:
        raise HTTPException(404, "patient not found")
    try:
        access_service.grant_access(db, x_clinician_id, patient.id, body.code)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    return {
        "patient_id": patient.id,
        "username": patient.username,
        "external_patient_id": patient.external_patient_id,
        "canonical_name": patient.canonical_name,
        "phone": patient.phone,
    }


@router.get("/clinician/patients")
def list_clinician_patients(
    x_clinician_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_clinician_id:
        raise HTTPException(401, "clinician session required")
    ids = access_service.clinician_patient_ids(db, x_clinician_id)
    patients = db.query(Patient).filter(Patient.id.in_(ids)).all() if ids else []
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
