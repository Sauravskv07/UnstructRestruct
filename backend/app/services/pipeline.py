from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db import models
from app.schemas.ir import DocumentIR
from app.services.extraction.classify import classify_document
from app.services.extraction.extract import extract_structured
from app.services.ingestion.extract_text import extract_document
from app.services.linking.patients import link_patient
from app.services.normalization.normalize import normalize_payload
from app.services.persistence.store import persist_canonical
from app.services.validation.validate import validate_canonical


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(doc: models.Document, stage: str, status: str, message: str = "") -> None:
    entries = json.loads(doc.processing_log or "[]")
    entries.append({"stage": stage, "status": status, "message": message, "ts": _now()})
    doc.processing_log = json.dumps(entries)
    doc.status = status
    doc.updated_at = datetime.now(timezone.utc)


def process_document(db: Session, document_id: str) -> models.Document:
    doc = db.get(models.Document, document_id)
    if doc is None:
        raise ValueError(f"document {document_id} not found")

    reasons: list[str] = []
    try:
        ir = extract_document(doc.id, doc.filename, doc.stored_path)
        _persist_ir(db, doc, ir)
        if ir.used_ocr:
            _log(doc, "ocr", "OCR_COMPLETED", f"{ir.page_count} page(s)")
        else:
            _log(doc, "text_extract", "TEXT_EXTRACTED", f"{ir.page_count} page(s)")
        db.commit()

        classification = classify_document(ir)
        doc.document_type = classification.document_type
        doc.classification_confidence = classification.confidence
        _log(doc, "classify", "CLASSIFIED", classification.reason or classification.document_type)
        db.commit()

        if classification.document_type == "unknown":
            reasons.append("unknown document type")
            _log(doc, "extract", "EXTRACTION_FAILED", "unknown document type")
            doc.needs_review = True
            doc.review_reasons = json.dumps(reasons)
            _log(doc, "complete", "NEEDS_REVIEW", "unknown document type")
            db.commit()
            db.refresh(doc)
            return doc

        extracted = extract_structured(ir, classification.document_type)
        _log(doc, "extract", "EXTRACTED", classification.document_type)
        db.commit()

        canonical = normalize_payload(doc.id, extracted)
        _log(doc, "normalize", "NORMALIZED")
        db.commit()

        issues = validate_canonical(canonical)
        failed = [i for i in issues if i.severity == "error"]
        if failed:
            reasons.extend(i.message for i in failed)
            _log(doc, "validate", "VALIDATION_FAILED", "; ".join(reasons[:5]))
        else:
            _log(doc, "validate", "VALIDATED")
        db.commit()

        link = link_patient(db, canonical)
        doc.patient_id = link.patient_id
        if link.needs_review:
            reasons.append(link.match_reason)
            _log(doc, "link", "LINKING_AMBIGUOUS", link.match_reason)
        else:
            _log(doc, "link", "LINKED", link.match_reason)
        db.commit()

        persist_canonical(db, doc, canonical, issues, link)
        if reasons or (doc.classification_confidence or 1) < 0.6:
            if (doc.classification_confidence or 1) < 0.6:
                reasons.append("low classification confidence")
            doc.needs_review = True
            doc.review_reasons = json.dumps(reasons)
            _log(doc, "complete", "NEEDS_REVIEW", "; ".join(reasons[:5]))
        else:
            doc.needs_review = False
            _log(doc, "complete", "COMPLETED")
        db.commit()
        db.refresh(doc)
        return doc
    except Exception as exc:  # noqa: BLE001 - surface stage failure to the document
        doc.error_message = str(exc)
        if doc.status in {"UPLOADED"}:
            _log(doc, "extract_text", "OCR_FAILED" if "tesseract" in str(exc).lower() else "EXTRACTION_FAILED", str(exc))
        elif doc.status in {"TEXT_EXTRACTED", "OCR_COMPLETED", "CLASSIFIED"}:
            _log(doc, "extract", "EXTRACTION_FAILED", str(exc))
        else:
            _log(doc, "pipeline", "EXTRACTION_FAILED", str(exc))
        doc.needs_review = True
        db.commit()
        db.refresh(doc)
        return doc


def _persist_ir(db: Session, doc: models.Document, ir: DocumentIR) -> None:
    doc.page_count = ir.page_count
    doc.has_native_text = ir.has_native_text
    doc.used_ocr = ir.used_ocr
    doc.media_type = ir.media_type
    doc.ir_json = ir.model_dump_json()
    doc.pages.clear()
    db.flush()
    for page in ir.pages:
        doc.pages.append(
            models.DocumentPage(
                document_id=doc.id,
                page_number=page.page_number,
                text=page.text,
                blocks_json=json.dumps([b.model_dump() for b in page.blocks]),
                ocr_used=page.ocr_used,
            )
        )
