from __future__ import annotations

import re

from app.config import settings
from app.schemas.extracted import ClassificationResult
from app.schemas.ir import DocumentIR
from app.services.extraction.gemini import classify_with_gemini
from app.services.extraction.llm import classify_with_llm


LAB_HINTS = (
    "lab report",
    "laboratory",
    "hemoglobin",
    "haemoglobin",
    "creatinine",
    "wbc",
    "test name",
    "reference range",
    "hba1c",
)
RX_HINTS = (
    "prescription",
    "rx",
    "tablet",
    "capsule",
    "sig:",
    "take ",
    "mg",
    "once daily",
    "bid",
    "tid",
)
DX_HINTS = (
    "diagnostic",
    "radiology",
    "impression",
    "findings",
    "chest x-ray",
    "mri",
    "ct scan",
    "ultrasound",
    "study:",
)


def classify_document(ir: DocumentIR) -> ClassificationResult:
    text = ir.combined_text(4000).lower()
    heuristic = _heuristic(text)
    if heuristic.confidence >= 0.85 or settings.resolved_llm_mode() == "stub":
        return heuristic
    if settings.resolved_llm_mode() == "gemini":
        llm = classify_with_gemini(ir)
    else:
        llm = classify_with_llm(ir)
    if llm.confidence >= heuristic.confidence:
        return llm
    return heuristic


def _heuristic(text: str) -> ClassificationResult:
    lab = _score(text, LAB_HINTS)
    rx = _score(text, RX_HINTS)
    dx = _score(text, DX_HINTS)
    scores = {
        "lab_report": lab,
        "prescription": rx,
        "diagnostic_report": dx,
    }
    winner = max(scores, key=scores.get)
    best = scores[winner]
    if best == 0:
        return ClassificationResult(document_type="unknown", confidence=0.2, reason="no type hints")
    total = sum(scores.values()) or 1
    confidence = min(0.95, 0.45 + 0.15 * best)
    if best < 2:
        confidence = min(confidence, 0.55)
    if list(scores.values()).count(best) > 1:
        return ClassificationResult(
            document_type="unknown",
            confidence=0.4,
            reason="ambiguous type hints",
        )
    return ClassificationResult(
        document_type=winner,  # type: ignore[arg-type]
        confidence=round(confidence, 2),
        reason=f"keyword score {best}/{total}",
    )


def _score(text: str, hints: tuple[str, ...]) -> int:
    return sum(1 for hint in hints if re.search(rf"\b{re.escape(hint)}\b", text) or hint in text)
