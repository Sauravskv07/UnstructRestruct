from pathlib import Path

import fitz

from app.services.ingestion.extract_text import extract_document, inspect_pdf_text_layer


def _write_text_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def test_native_text_extraction(tmp_path: Path):
    pdf = tmp_path / "native.pdf"
    _write_text_pdf(pdf, "Laboratory Report Haemoglobin 13.2 g/dL Creatinine 0.9 mg/dL")
    page_count, has_text, total = inspect_pdf_text_layer(pdf)
    assert page_count == 1
    assert has_text
    assert total > 10

    ir = extract_document("doc-1", "native.pdf", str(pdf))
    assert ir.has_native_text
    assert not ir.used_ocr
    assert "Haemoglobin" in ir.pages[0].text
    assert ir.pages[0].blocks


def test_image_only_pdf_has_no_text_layer(tmp_path: Path):
    src = tmp_path / "src.pdf"
    _write_text_pdf(src, "Haemoglobin 13.2 g/dL")
    scanned = tmp_path / "scanned.pdf"
    src_doc = fitz.open(src)
    out = fitz.open()
    pix = src_doc[0].get_pixmap(dpi=120)
    page = out.new_page(width=src_doc[0].rect.width, height=src_doc[0].rect.height)
    page.insert_image(page.rect, pixmap=pix)
    out.save(scanned)
    out.close()
    src_doc.close()

    _, has_text, total = inspect_pdf_text_layer(scanned)
    assert not has_text
    assert total < 40
