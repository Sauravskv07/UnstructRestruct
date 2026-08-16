from __future__ import annotations

from openai import OpenAI

from app.config import settings
from app.schemas.extracted import (
    ClassificationResult,
    DiagnosticReportExtract,
    LabReportExtract,
    PrescriptionExtract,
)
from app.schemas.ir import DocumentIR


SYSTEM = """You extract structured medical document fields.
Use only information present in the provided text.
If a field is not present, return null. Do not invent units, reference ranges, diagnoses, or values.
Cite the page number from [PAGE N] markers and a short source_text span for each extracted item.
Do not normalize values; return them as written.
Patient identity is name and phone. patient_id is a hospital MRN or similar label only, not the person's identity.
"""


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=settings.openai_api_key)


def classify_with_llm(ir: DocumentIR) -> ClassificationResult:
    client = _client()
    completion = client.beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": "Classify the document as lab_report, prescription, diagnostic_report, or unknown. Do not guess if evidence is weak.",
            },
            {"role": "user", "content": ir.combined_text(3500)},
        ],
        response_format=ClassificationResult,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        return ClassificationResult(document_type="unknown", confidence=0.2, reason="llm parse failed")
    return parsed


def extract_with_llm(
    ir: DocumentIR, document_type: str
) -> LabReportExtract | PrescriptionExtract | DiagnosticReportExtract:
    schema_map = {
        "lab_report": LabReportExtract,
        "prescription": PrescriptionExtract,
        "diagnostic_report": DiagnosticReportExtract,
    }
    schema = schema_map[document_type]
    client = _client()
    completion = client.beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Document type: {document_type}\n\n{ir.combined_text()}",
            },
        ],
        response_format=schema,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("LLM structured extraction returned no parsed object")
    return parsed
