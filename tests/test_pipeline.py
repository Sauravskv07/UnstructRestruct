from pathlib import Path

import fitz

from app.db.models import Document, LabResult
from app.services.pipeline import process_document


def _pdf(path: Path, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 18
    doc.save(path)
    doc.close()


def test_end_to_end_lab_pipeline(db, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "stub")
    from app.config import settings

    monkeypatch.setattr(settings, "llm_mode", "stub")

    pdf = tmp_path / "lab.pdf"
    _pdf(
        pdf,
        [
            "Laboratory Report",
            "Patient Name: Aarav Sharma",
            "Patient ID: PAT-1001",
            "DOB: 14 Mar 1988",
            "Date: 12-Jul-2026",
            "Haemoglobin          13.2       g/DL     13.0 - 17.0",
        ],
    )
    doc = Document(filename="lab.pdf", stored_path=str(pdf), status="UPLOADED")
    db.add(doc)
    db.commit()

    processed = process_document(db, doc.id)
    assert processed.document_type == "lab_report"
    assert processed.status in {"COMPLETED", "NEEDS_REVIEW"}
    assert processed.document_date == "2026-07-12"
    results = db.query(LabResult).filter(LabResult.document_id == doc.id).all()
    assert results
    hb = next(r for r in results if r.canonical_name == "hemoglobin")
    assert hb.value == 13.2
    assert hb.unit == "g/dL"
    assert hb.raw_name == "Haemoglobin"
    assert processed.patient_id is not None


def test_inconsistent_lab_is_not_silently_accepted(db, tmp_path: Path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "llm_mode", "stub")
    pdf = tmp_path / "bad.pdf"
    _pdf(
        pdf,
        [
            "Laboratory Report",
            "Patient Name: Aarav Sharma",
            "Patient ID: PAT-1001",
            "Date: 15 Jul 2026",
            "Haemoglobin          13.2       g/dL     13.0 - 17.0",
            "Hemoglobin           8.1        g/dL     13.0 - 17.0",
        ],
    )
    doc = Document(filename="bad.pdf", stored_path=str(pdf), status="UPLOADED")
    db.add(doc)
    db.commit()
    processed = process_document(db, doc.id)
    assert processed.needs_review
    assert processed.status in {"NEEDS_REVIEW", "VALIDATION_FAILED"}
    assert processed.validation_errors
    assert any(e.code == "inconsistent_values" for e in processed.validation_errors)
