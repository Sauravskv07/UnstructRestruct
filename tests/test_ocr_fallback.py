from app.schemas.ir import PageIR, TextBlock
from app.services.ingestion.ocr import should_use_vision_ocr


def test_vision_off_without_openai(monkeypatch):
    monkeypatch.setattr("app.services.ingestion.ocr.settings.openai_api_key", None)
    monkeypatch.setattr("app.services.ingestion.ocr.settings.gemini_api_key", None)
    monkeypatch.setattr("app.services.ingestion.ocr.settings.llm_mode", "stub")
    page = PageIR(page_number=1, text="", ocr_used=True)
    assert not should_use_vision_ocr(page, source="image", tesseract_error="missing")


def test_vision_on_tesseract_error(monkeypatch):
    monkeypatch.setattr("app.services.ingestion.ocr.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("app.services.ingestion.ocr.settings.llm_mode", "openai")
    page = PageIR(page_number=1, text="", ocr_used=True)
    assert should_use_vision_ocr(page, source="pdf", tesseract_error="tesseract missing")


def test_vision_on_phone_photo(monkeypatch):
    monkeypatch.setattr("app.services.ingestion.ocr.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("app.services.ingestion.ocr.settings.llm_mode", "openai")
    page = PageIR(
        page_number=1,
        text="NUTEMA HOSPITAL Department of Urology " * 5,
        ocr_used=True,
        blocks=[TextBlock(text="NUTEMA", confidence=0.95)],
    )
    assert should_use_vision_ocr(page, source="image")
    assert not should_use_vision_ocr(page, source="pdf")


def test_vision_on_thin_or_low_confidence_pdf_ocr(monkeypatch):
    monkeypatch.setattr("app.services.ingestion.ocr.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("app.services.ingestion.ocr.settings.llm_mode", "openai")
    thin = PageIR(page_number=1, text="abc", ocr_used=True)
    assert should_use_vision_ocr(thin, source="pdf")
    low = PageIR(
        page_number=1,
        text="word " * 40,
        ocr_used=True,
        blocks=[
            TextBlock(text="a", confidence=0.2),
            TextBlock(text="b", confidence=0.2),
            TextBlock(text="c", confidence=0.2),
        ],
    )
    assert should_use_vision_ocr(low, source="pdf")
