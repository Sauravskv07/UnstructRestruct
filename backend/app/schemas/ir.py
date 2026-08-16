from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    text: str
    bbox: tuple[float, float, float, float] | None = None
    confidence: float | None = None


class PageIR(BaseModel):
    page_number: int
    text: str
    blocks: list[TextBlock] = Field(default_factory=list)
    ocr_used: bool = False


class DocumentIR(BaseModel):
    document_id: str
    filename: str
    media_type: str
    page_count: int
    has_native_text: bool
    used_ocr: bool = False
    pages: list[PageIR] = Field(default_factory=list)

    def combined_text(self, max_chars: int = 12000) -> str:
        parts: list[str] = []
        for page in self.pages:
            parts.append(f"[PAGE {page.page_number}]\n{page.text}")
        text = "\n\n".join(parts)
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n\n[TRUNCATED]"
