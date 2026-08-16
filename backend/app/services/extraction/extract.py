from __future__ import annotations

from app.config import settings
from app.schemas.extracted import (
    DiagnosticReportExtract,
    LabReportExtract,
    PrescriptionExtract,
)
from app.schemas.ir import DocumentIR
from app.services.extraction.gemini import extract_with_gemini
from app.services.extraction.llm import extract_with_llm
from app.services.extraction.stub import extract_with_stub


Extracted = LabReportExtract | PrescriptionExtract | DiagnosticReportExtract


def extract_structured(ir: DocumentIR, document_type: str) -> Extracted:
    if document_type == "unknown":
        return LabReportExtract(patient={}, tests=[])
    if settings.resolved_llm_mode() == "stub":
        return extract_with_stub(ir, document_type)
    if settings.resolved_llm_mode() == "gemini":
        return extract_with_gemini(ir, document_type)
    return extract_with_llm(ir, document_type)
