from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import BACKEND_ROOT, settings
from app.db.models import Document, Patient
from app.db.session import SessionLocal, get_db
from app.services import access as access_service
from app.services.linking.identity import identity_warnings, target_identity_compatible
from app.services.linking.patients import _maybe_fill
from app.services.normalization.names import normalize_person_name
from app.services.normalization.phones import normalize_phone
from app.services.pipeline import process_document

router = APIRouter(prefix="/documents", tags=["documents"])

PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
PROCESSING = "PROCESSING"
FAILED = "FAILED"
CANCELLED = "CANCELLED"


def _upload_dir() -> Path:
    path = Path(settings.upload_dir)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _visible_ids(
    db: Session,
    x_app_role: str | None,
    x_patient_id: str | None,
    x_clinician_id: str | None,
) -> list[str]:
    return access_service.visible_patient_ids(db, x_app_role, x_patient_id, x_clinician_id)


def _can_view_doc(
    db: Session,
    doc: Document,
    x_app_role: str | None,
    x_patient_id: str | None,
    x_clinician_id: str | None,
) -> bool:
    allowed = _visible_ids(db, x_app_role, x_patient_id, x_clinician_id)
    if not allowed:
        return False
    return doc.patient_id in allowed


def _assign_patient(doc: Document, patient_id: str | None) -> None:
    doc.patient_id = patient_id
    for row in doc.lab_results:
        row.patient_id = patient_id
    for row in doc.medications:
        row.patient_id = patient_id
    if doc.diagnostic_report is not None:
        doc.diagnostic_report.patient_id = patient_id


def _extracted_patient(doc: Document) -> dict:
    if not doc.extracted_json:
        return {"name": None, "patient_id": None, "date_of_birth": None, "phone": None}
    payload = json.loads(doc.extracted_json)
    patient = payload.get("patient") or {}
    return {
        "name": patient.get("name"),
        "patient_id": patient.get("patient_id"),
        "date_of_birth": patient.get("date_of_birth"),
        "phone": patient.get("phone"),
    }


def _discard_failed_upload(db: Session, doc: Document, keep_patient_id: str | None = None) -> None:
    stored = Path(doc.stored_path) if doc.stored_path else None
    linked_patient_id = doc.patient_id
    attached = db.merge(doc)
    db.delete(attached)
    db.flush()
    if linked_patient_id and linked_patient_id != keep_patient_id:
        remaining = (
            db.query(Document).filter(Document.patient_id == linked_patient_id).count()
        )
        if remaining == 0:
            patient = db.get(Patient, linked_patient_id)
            if patient is not None:
                db.delete(patient)
    db.commit()
    if stored and stored.exists():
        stored.unlink()


def _extracted_text(doc: Document) -> str:
    pages = sorted(doc.pages, key=lambda item: item.page_number)
    chunks = [page.text.strip() for page in pages if page.text and page.text.strip()]
    return "\n\n".join(chunks)


def _confirmation_payload(db: Session, doc: Document, target: Patient) -> dict:
    extracted = _extracted_patient(doc)
    return {
        "needs_confirmation": True,
        "id": doc.id,
        "document": _document_detail(db, doc),
        "extracted_text": _extracted_text(doc),
        "ocr_error": doc.error_message,
        "extracted_patient": extracted,
        "chart_patient": {
            "name": target.canonical_name,
            "phone": target.phone,
            "username": target.username,
            "patient_id": target.external_patient_id,
            "date_of_birth": target.date_of_birth,
        },
        "warnings": identity_warnings(
            extracted["name"], extracted["phone"], extracted["date_of_birth"], target
        ),
    }


def _apply_extracted_identity(patient: Patient, extracted: dict) -> None:
    name = extracted.get("name")
    phone = extracted.get("phone")
    _maybe_fill(
        patient,
        name,
        normalize_person_name(name),
        extracted.get("date_of_birth"),
        extracted.get("patient_id"),
        phone,
        normalize_phone(phone),
    )


def _finalize_confirmed_document(doc: Document, patient: Patient) -> None:
    errors = [row.message for row in doc.validation_errors if row.severity == "error"]
    patient.needs_review = False
    if errors:
        doc.needs_review = True
        doc.review_reasons = json.dumps(errors)
        doc.status = "NEEDS_REVIEW"
        return
    doc.needs_review = False
    doc.review_reasons = "[]"
    doc.status = "COMPLETED"


def _drop_empty_patient(db: Session, patient_id: str | None, keep_patient_id: str | None) -> None:
    if not patient_id or patient_id == keep_patient_id:
        return
    remaining = db.query(Document).filter(Document.patient_id == patient_id).count()
    if remaining == 0:
        extra = db.get(Patient, patient_id)
        if extra is not None:
            db.delete(extra)


def _run_pipeline_job(document_id: str, target_patient_id: str) -> None:
    db = SessionLocal()
    try:
        current = db.get(Document, document_id)
        if current is None or current.status == CANCELLED:
            if current is not None:
                _discard_failed_upload(db, current, keep_patient_id=target_patient_id)
            return
        doc = process_document(db, document_id)
        current = db.get(Document, document_id)
        if current is None or current.status == CANCELLED:
            if current is not None:
                _discard_failed_upload(db, current, keep_patient_id=target_patient_id)
            return
        target_patient = db.get(Patient, target_patient_id)
        if target_patient is None:
            doc.status = FAILED
            doc.error_message = "patient not found"
            db.commit()
            return
        linked_id = doc.patient_id
        _assign_patient(doc, target_patient_id)
        _drop_empty_patient(db, linked_id, target_patient_id)
        if doc.error_message and not doc.extracted_json:
            doc.status = FAILED
        else:
            doc.status = PENDING_CONFIRMATION
        db.commit()
    except Exception as exc:  # noqa: BLE001 - persist failure for the poller
        failed = db.get(Document, document_id)
        if failed is not None and failed.status != CANCELLED:
            failed.status = FAILED
            failed.error_message = str(exc)
            db.commit()
    finally:
        db.close()


@router.post("")
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_patient_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    if not file.filename:
        raise HTTPException(400, "filename required")
    allowed = _visible_ids(db, x_app_role, x_patient_id, x_clinician_id)
    if x_app_role == "patient":
        target = x_patient_id
    elif x_app_role == "clinician":
        if not target_patient_id:
            raise HTTPException(400, "select a patient you have access to")
        if target_patient_id not in allowed:
            raise HTTPException(403, "no access to upload for this patient")
        target = target_patient_id
    else:
        raise HTTPException(401, "sign in required")
    if not target:
        raise HTTPException(401, "sign in required")

    doc = Document(
        filename=file.filename,
        stored_path="",
        status=PROCESSING,
        patient_id=target,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    dest = _upload_dir() / f"{doc.id}_{file.filename}"
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    doc.stored_path = str(dest)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_pipeline_job, doc.id, target)
    return {
        **_document_summary(db, doc),
        "poll_url": f"/documents/{doc.id}",
    }


@router.get("")
def list_documents(
    needs_review: bool | None = None,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    allowed = _visible_ids(db, x_app_role, x_patient_id, x_clinician_id)
    if not allowed:
        return []
    query = db.query(Document).filter(
        Document.patient_id.in_(allowed),
        Document.status != CANCELLED,
    ).order_by(Document.created_at.desc())
    if needs_review is True:
        query = query.filter(Document.needs_review.is_(True))
    return [_document_summary(db, doc) for doc in query.all()]


@router.get("/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if not _can_view_doc(db, doc, x_app_role, x_patient_id, x_clinician_id):
        raise HTTPException(403, "no access to this document")
    payload = _document_detail(db, doc)
    if doc.status == PENDING_CONFIRMATION:
        patient = db.get(Patient, doc.patient_id) if doc.patient_id else None
        if patient is not None:
            payload["confirmation"] = _confirmation_payload(db, doc, patient)
    return payload


@router.post("/{document_id}/confirm")
def confirm_document(
    document_id: str,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    if x_app_role not in {"patient", "clinician"}:
        raise HTTPException(401, "sign in required")
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc.status not in {PENDING_CONFIRMATION, "NEEDS_REVIEW"}:
        raise HTTPException(409, "document is not waiting for confirmation")
    if not _can_view_doc(db, doc, x_app_role, x_patient_id, x_clinician_id):
        raise HTTPException(403, "no access to this document")
    if x_app_role == "patient" and doc.patient_id != x_patient_id:
        raise HTTPException(409, "document is not waiting for your confirmation")
    patient = db.get(Patient, doc.patient_id)
    if patient is None:
        raise HTTPException(404, "patient not found")
    extracted = _extracted_patient(doc)
    _apply_extracted_identity(patient, extracted)
    _assign_patient(doc, patient.id)
    _finalize_confirmed_document(doc, patient)
    db.commit()
    db.refresh(doc)
    return _document_detail(db, doc)


@router.post("/{document_id}/discard")
def discard_document(
    document_id: str,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    if x_app_role not in {"patient", "clinician"}:
        raise HTTPException(401, "sign in required")
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc.status not in {PENDING_CONFIRMATION, PROCESSING, FAILED}:
        raise HTTPException(409, "document cannot be discarded")
    if not _can_view_doc(db, doc, x_app_role, x_patient_id, x_clinician_id):
        raise HTTPException(403, "no access to this document")
    if x_app_role == "patient" and doc.patient_id != x_patient_id:
        raise HTTPException(409, "document is not waiting for your confirmation")
    if doc.status == PROCESSING:
        doc.status = CANCELLED
        db.commit()
    _discard_failed_upload(db, doc, keep_patient_id=doc.patient_id)
    return {"ok": True}


@router.post("/{document_id}/reprocess")
def reprocess(
    document_id: str,
    db: Session = Depends(get_db),
    x_app_role: str | None = Header(default=None),
    x_patient_id: str | None = Header(default=None),
    x_clinician_id: str | None = Header(default=None),
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if not _can_view_doc(db, doc, x_app_role, x_patient_id, x_clinician_id):
        raise HTTPException(403, "no access to this document")
    owner = doc.patient_id
    doc.status = "UPLOADED"
    doc.error_message = None
    db.commit()
    doc = process_document(db, doc.id)
    if owner:
        owner_patient = db.get(Patient, owner)
        if owner_patient is not None:
            extracted = _extracted_patient(doc)
            ok, reason = target_identity_compatible(
                extracted["name"], extracted["phone"], extracted["date_of_birth"], owner_patient
            )
            if not ok:
                _assign_patient(doc, owner)
                db.commit()
                raise HTTPException(409, reason)
        _assign_patient(doc, owner)
        db.commit()
        db.refresh(doc)
    return _document_detail(db, doc)


def _document_summary(db: Session, doc: Document) -> dict:
    patient = db.get(Patient, doc.patient_id) if doc.patient_id else None
    return {
        "id": doc.id,
        "filename": doc.filename,
        "document_type": doc.document_type,
        "status": doc.status,
        "patient_id": doc.patient_id,
        "patient_name": patient.canonical_name if patient else None,
        "document_date": doc.document_date,
        "needs_review": doc.needs_review,
        "page_count": doc.page_count,
        "used_ocr": doc.used_ocr,
        "has_native_text": doc.has_native_text,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def _document_detail(db: Session, doc: Document) -> dict:
    patient = db.get(Patient, doc.patient_id) if doc.patient_id else None
    pages = [
        {"page_number": p.page_number, "text": p.text, "ocr_used": p.ocr_used}
        for p in sorted(doc.pages, key=lambda item: item.page_number)
    ]
    return {
        **_document_summary(db, doc),
        "review_reasons": json.loads(doc.review_reasons or "[]"),
        "processing_log": json.loads(doc.processing_log or "[]"),
        "error_message": doc.error_message,
        "extracted": json.loads(doc.extracted_json) if doc.extracted_json else None,
        "pages": pages,
        "validation_errors": [
            {
                "entity_type": e.entity_type,
                "field": e.field,
                "code": e.code,
                "message": e.message,
                "severity": e.severity,
            }
            for e in doc.validation_errors
        ],
        "link": (
            {
                "match_method": doc.links[-1].match_method,
                "match_reason": doc.links[-1].match_reason,
                "confidence": doc.links[-1].confidence,
                "needs_review": doc.links[-1].needs_review,
                "candidate_patient_ids": json.loads(doc.links[-1].candidate_patient_ids or "[]"),
            }
            if doc.links
            else None
        ),
        "patient": (
            {
                "id": patient.id,
                "canonical_name": patient.canonical_name,
                "phone": patient.phone,
                "username": patient.username,
                "external_patient_id": patient.external_patient_id,
                "date_of_birth": patient.date_of_birth,
                "needs_review": patient.needs_review,
            }
            if patient
            else None
        ),
    }
