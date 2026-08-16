from __future__ import annotations

from pathlib import Path

import fitz

from app.schemas.ir import DocumentIR, PageIR, TextBlock
from app.services.ingestion.ocr import ocr_image_file, ocr_pixmap


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
NATIVE_TEXT_MIN_CHARS = 40


def extract_document(document_id: str, filename: str, stored_path: str) -> DocumentIR:
    path = Path(stored_path)
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return _extract_image(document_id, filename, path)
    return _extract_pdf(document_id, filename, path)


def inspect_pdf_text_layer(path: Path) -> tuple[int, bool, int]:
    doc = fitz.open(path)
    try:
        total = 0
        for page in doc:
            total += len(page.get_text("text").strip())
        has_text = total >= NATIVE_TEXT_MIN_CHARS
        return doc.page_count, has_text, total
    finally:
        doc.close()


def _extract_pdf(document_id: str, filename: str, path: Path) -> DocumentIR:
    page_count, has_native, _ = inspect_pdf_text_layer(path)
    doc = fitz.open(path)
    pages: list[PageIR] = []
    used_ocr = False
    try:
        for index, page in enumerate(doc, start=1):
            if has_native:
                pages.append(_native_page(page, index))
            else:
                used_ocr = True
                pages.append(_ocr_page(page, index))
    finally:
        doc.close()
    return DocumentIR(
        document_id=document_id,
        filename=filename,
        media_type="pdf",
        page_count=page_count,
        has_native_text=has_native,
        used_ocr=used_ocr,
        pages=pages,
    )


def _extract_image(document_id: str, filename: str, path: Path) -> DocumentIR:
    ir_page = ocr_image_file(path, page_number=1)
    return DocumentIR(
        document_id=document_id,
        filename=filename,
        media_type="image",
        page_count=1,
        has_native_text=False,
        used_ocr=True,
        pages=[ir_page],
    )


def _native_page(page: fitz.Page, page_number: int) -> PageIR:
    text = page.get_text("text")
    blocks: list[TextBlock] = []
    raw = page.get_text("dict")
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = []
        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", []))
            if line_text.strip():
                lines.append(line_text)
        joined = "\n".join(lines).strip()
        if not joined:
            continue
        bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
        blocks.append(TextBlock(text=joined, bbox=bbox, confidence=1.0))
    return PageIR(page_number=page_number, text=text, blocks=blocks, ocr_used=False)


def _ocr_page(page: fitz.Page, page_number: int) -> PageIR:
    pix = page.get_pixmap(dpi=200)
    return ocr_pixmap(pix, page_number=page_number)
