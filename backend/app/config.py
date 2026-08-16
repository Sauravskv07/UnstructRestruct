from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


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
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    demo_patient_password: str = "demo"

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
