from __future__ import annotations

import json
import re

import httpx

from app.config import settings
from app.schemas.extracted import (
    ClassificationResult,
    DiagnosticReportExtract,
    LabReportExtract,
    PrescriptionExtract,
)
from app.schemas.ir import DocumentIR
from app.services.extraction.llm import SYSTEM

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def classify_with_gemini(ir: DocumentIR) -> ClassificationResult:
    prompt = (
        "Classify this medical document as lab_report, prescription, "
        "diagnostic_report, or unknown. Do not guess if evidence is weak.\n"
        "Return JSON with keys document_type, confidence (0-1), reason.\n\n"
        f"{ir.combined_text(3500)}"
    )
    data = _generate_json(prompt)
    try:
        return ClassificationResult.model_validate(data)
    except Exception:
        return ClassificationResult(document_type="unknown", confidence=0.2, reason="gemini parse failed")


def extract_with_gemini(
    ir: DocumentIR, document_type: str
) -> LabReportExtract | PrescriptionExtract | DiagnosticReportExtract:
    schema_map = {
        "lab_report": LabReportExtract,
        "prescription": PrescriptionExtract,
        "diagnostic_report": DiagnosticReportExtract,
    }
    schema = schema_map[document_type]
    prompt = (
        f"{SYSTEM}\nDocument type: {document_type}\n"
        f"Return JSON matching this schema:\n{json.dumps(schema.model_json_schema())}\n\n"
        f"{ir.combined_text()}"
    )
    data = _generate_json(prompt)
    return schema.model_validate(data)


def transcribe_with_gemini(image_jpeg: bytes) -> str:
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Transcribe every readable character on this medical document photo. "
                            "Include printed letterhead and handwritten notes. "
                            "Preserve line breaks. Do not invent names, drugs, doses, or values. "
                            "If a word is illegible, write [illegible]."
                        )
                    },
                    {"inline_data": {"mime_type": "image/jpeg", "data": _b64(image_jpeg)}},
                ]
            }
        ]
    }
    data = _post(payload)
    return _text_from(data)


def _b64(raw: bytes) -> str:
    import base64

    return base64.b64encode(raw).decode("ascii")


def _generate_json(prompt: str) -> dict:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    data = _post(payload)
    text = _text_from(data)
    return _parse_json(text)


def _post(payload: dict) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    url = GEMINI_URL.format(model=settings.gemini_model)
    response = httpx.post(
        url,
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": settings.gemini_api_key,
        },
        json=payload,
        timeout=90.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini HTTP {response.status_code}: {response.text[:400]}")
    return response.json()


def _text_from(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(part.get("text") or "" for part in parts).strip()


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)
