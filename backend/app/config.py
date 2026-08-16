import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
_LOCAL_CORS = (
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
)


def running_on_railway() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"
    llm_mode: str = "auto"
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    tesseract_cmd: str | None = None
    cors_origins: str = _LOCAL_CORS
    demo_patient_password: str = "demo"

    @model_validator(mode="after")
    def apply_railway_defaults(self):
        if not running_on_railway():
            return self
        if self.database_url == "sqlite:///./data/app.db" and not os.getenv("DATABASE_URL"):
            self.database_url = "sqlite:////data/app.db"
        if self.upload_dir == "./data/uploads" and not os.getenv("UPLOAD_DIR"):
            self.upload_dir = "/data/uploads"
        if self.cors_origins == _LOCAL_CORS and not os.getenv("CORS_ORIGINS"):
            self.cors_origins = "*"
        return self

    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if raw == "*":
            return ["*"]
        return [part.strip() for part in raw.split(",") if part.strip()]

    def resolved_llm_mode(self) -> str:
        mode = (self.llm_mode or "auto").lower()
        if mode == "auto":
            if self.gemini_api_key:
                return "gemini"
            if self.openai_api_key:
                return "openai"
            return "stub"
        return mode

    def llm_available(self) -> bool:
        return self.resolved_llm_mode() in {"gemini", "openai"}


settings = Settings()
