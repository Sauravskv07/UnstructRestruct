from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import BACKEND_ROOT, settings


class Base(DeclarativeBase):
    pass


def _sqlite_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        rest = url.removeprefix("sqlite:///")
        db_path = Path(rest)
        if not db_path.is_absolute():
            db_path = BACKEND_ROOT / rest
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"
    return url


engine = create_engine(
    _sqlite_url(),
    connect_args={"check_same_thread": False, "timeout": 30},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def _sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
