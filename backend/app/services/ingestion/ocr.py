from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image
import pytesseract
from pytesseract import Output

from app.config import settings
from app.schemas.ir import PageIR, TextBlock
from app.services.ingestion.vision import transcribe_image_with_vision

# Phone photos can be 90MP+. Pillow warns at ~89MP; we downscale before OCR.
Image.MAX_IMAGE_PIXELS = None
MAX_OCR_SIDE = 2400
VISION_MIN_CHARS = 100
VISION_MIN_MEAN_CONF = 0.55

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
else:
    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ):
        if candidate.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            break


def ocr_image_file(path: Path, page_number: int = 1) -> PageIR:
    with Image.open(path) as raw:
        return ocr_with_fallback(raw, page_number, source="image")


def ocr_pixmap(pix: fitz.Pixmap, page_number: int) -> PageIR:
    image = Image.open(BytesIO(pix.tobytes("png")))
    return ocr_with_fallback(image, page_number, source="pdf")


def ocr_with_fallback(image: Image.Image, page_number: int, source: str) -> PageIR:
    prepared = _prepare_for_ocr(image)
    tesseract_error: str | None = None
    try:
        page = ocr_pil_image(prepared, page_number)
    except RuntimeError as exc:
        tesseract_error = str(exc)
        page = PageIR(page_number=page_number, text="", blocks=[], ocr_used=True)

    if should_use_vision_ocr(page, source=source, tesseract_error=tesseract_error):
        vision_text = transcribe_image_with_vision(prepared)
        if vision_text:
            page.text = vision_text
            page.blocks = [TextBlock(text=vision_text, confidence=None)]
            page.ocr_used = True
            return page
        if tesseract_error and not page.text.strip():
            raise RuntimeError(tesseract_error)
        return page

    if tesseract_error:
        raise RuntimeError(tesseract_error)
    return page


def should_use_vision_ocr(
    page: PageIR,
    source: str,
    tesseract_error: str | None = None,
) -> bool:
    """When Tesseract is not enough, use the vision model. See decision.md."""
    if not settings.llm_available():
        return False
    if tesseract_error:
        return True
    text = (page.text or "").strip()
    if source == "image":
        return True
    if len(text) < VISION_MIN_CHARS:
        return True
    confs = [block.confidence for block in page.blocks if block.confidence is not None]
    if len(confs) >= 3 and (sum(confs) / len(confs)) < VISION_MIN_MEAN_CONF:
        return True
    return False


def ocr_pil_image(image: Image.Image, page_number: int) -> PageIR:
    prepared = _prepare_for_ocr(image)
    try:
        data = pytesseract.image_to_data(prepared, output_type=Output.DICT)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract is not installed or TESSERACT_CMD is not set. "
            "Native-text PDFs still work; photos and scanned documents require local OCR."
        ) from exc

    blocks: list[TextBlock] = []
    lines: dict[tuple[int, int], list[str]] = {}
    n = len(data["text"])
    for i in range(n):
        word = (data["text"][i] or "").strip()
        if not word:
            continue
        conf_raw = data["conf"][i]
        try:
            conf = float(conf_raw) / 100.0 if float(conf_raw) >= 0 else None
        except (TypeError, ValueError):
            conf = None
        left, top, width, height = (
            float(data["left"][i]),
            float(data["top"][i]),
            float(data["width"][i]),
            float(data["height"][i]),
        )
        bbox = (left, top, left + width, top + height)
        blocks.append(TextBlock(text=word, bbox=bbox, confidence=conf))
        key = (int(data["block_num"][i]), int(data["line_num"][i]))
        lines.setdefault(key, []).append(word)

    text = "\n".join(" ".join(words) for _, words in sorted(lines.items()))
    return PageIR(page_number=page_number, text=text, blocks=blocks, ocr_used=True)


def _prepare_for_ocr(image: Image.Image) -> Image.Image:
    prepared = image.convert("RGB") if image.mode not in {"RGB", "L"} else image.copy()
    width, height = prepared.size
    longest = max(width, height)
    if longest > MAX_OCR_SIDE:
        scale = MAX_OCR_SIDE / longest
        prepared = prepared.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
    return prepared
