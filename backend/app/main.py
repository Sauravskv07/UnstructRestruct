from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.access import router as access_router
from app.api.documents import router as documents_router
from app.api.patients import router as patients_router
from app.api.queries import router as queries_router
from app.config import BACKEND_ROOT, REPO_ROOT, settings
from app.db.models import Base, Clinician
from app.db.session import SessionLocal, engine
from app.services.vocab import backfill_vocabulary, seed_vocabulary

DIST = REPO_ROOT / "frontend" / "dist"
API_ROOTS = {
    "documents",
    "patients",
    "query",
    "health",
    "auth",
    "me",
    "docs",
    "redoc",
    "openapi.json",
    "assets",
}

app = FastAPI(title="UnstructRestruct", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials="*" not in settings.cors_origin_list(),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(access_router)
app.include_router(documents_router)
app.include_router(patients_router)
app.include_router(queries_router)


def _ensure_sqlite_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        if "patients" in inspector.get_table_names():
            columns = {col["name"] for col in inspector.get_columns("patients")}
            if "password_hash" not in columns:
                conn.execute(text("ALTER TABLE patients ADD COLUMN password_hash VARCHAR"))
            if "username" not in columns:
                conn.execute(text("ALTER TABLE patients ADD COLUMN username VARCHAR"))
            if "phone" not in columns:
                conn.execute(text("ALTER TABLE patients ADD COLUMN phone VARCHAR"))
            if "normalized_phone" not in columns:
                conn.execute(text("ALTER TABLE patients ADD COLUMN normalized_phone VARCHAR"))
            conn.execute(
                text(
                    "UPDATE patients SET username = external_patient_id "
                    "WHERE username IS NULL AND external_patient_id IS NOT NULL"
                )
            )
        if "clinicians" in inspector.get_table_names():
            columns = {col["name"] for col in inspector.get_columns("clinicians")}
            if "password_hash" not in columns:
                conn.execute(text("ALTER TABLE clinicians ADD COLUMN password_hash VARCHAR"))
        if "diagnostic_reports" in inspector.get_table_names():
            columns = {col["name"] for col in inspector.get_columns("diagnostic_reports")}
            if "canonical_study" not in columns:
                conn.execute(text("ALTER TABLE diagnostic_reports ADD COLUMN canonical_study VARCHAR"))


@app.on_event("startup")
def startup() -> None:
    upload_dir = Path(settings.upload_dir)
    if not upload_dir.is_absolute():
        upload_dir = BACKEND_ROOT / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
    db = SessionLocal()
    try:
        if db.query(Clinician).filter(Clinician.external_id == "DOC-1001").one_or_none() is None:
            db.add(Clinician(external_id="DOC-1001", name="Dr. Meera Kapoor"))
        seed_vocabulary(db)
        backfill_vocabulary(db)
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


if DIST.is_dir() and (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


def _is_api_path(path: str) -> bool:
    stripped = path.lstrip("/")
    if stripped.startswith("clinician/patients"):
        return True
    root = stripped.split("/", 1)[0]
    return root in API_ROOTS


def _index_response():
    index = DIST / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-store"})
    return None


@app.exception_handler(404)
async def spa_or_404(request: Request, _exc: HTTPException):
    path = request.url.path
    if request.method == "GET" and DIST.is_dir() and not _is_api_path(path):
        candidate = DIST / path.lstrip("/")
        if path not in {"/", ""} and candidate.is_file():
            return FileResponse(candidate)
        index = _index_response()
        if index is not None:
            return index
    return JSONResponse({"detail": "Not Found"}, status_code=404)


@app.get("/", response_model=None)
def root():
    index = _index_response()
    if index is not None:
        return index
    return JSONResponse(
        {
            "detail": "Frontend is not built. From frontend/ run: npm install && npm run build",
            "health": "/health",
        },
        status_code=503,
    )
