from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.config import settings


VISION_TRANSCRIBE = (
    "Transcribe every readable character on this medical document photo. "
    "Include printed letterhead and handwritten notes. "
    "Preserve line breaks. Do not invent names, drugs, doses, or values. "
    "If a word is illegible, write [illegible]."
)


def transcribe_image_with_vision(image: Image.Image) -> str:
    if not settings.llm_available():
        raise RuntimeError("vision OCR requires GEMINI_API_KEY or OPENAI_API_KEY")
    buffer = BytesIO()
    rgb = image.convert("RGB") if image.mode != "RGB" else image
    rgb.save(buffer, format="JPEG", quality=85)
    jpeg = buffer.getvalue()
    if settings.resolved_llm_mode() == "gemini":
        from app.services.extraction.gemini import transcribe_with_gemini

        return transcribe_with_gemini(jpeg)
    return _transcribe_openai(jpeg)


def _transcribe_openai(jpeg: bytes) -> str:
    import base64

    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = base64.b64encode(jpeg).decode("ascii")
    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_TRANSCRIBE},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{payload}"},
                    },
                ],
            }
        ],
    )
    return (completion.choices[0].message.content or "").strip()
