from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db import models

_PBKDF2_ROUNDS = 80_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, salt_hex, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _PBKDF2_ROUNDS
    )
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))


CODE_TTL = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def generate_code(db: Session, patient_id: str) -> models.ShareCode:
    existing = (
        db.query(models.ShareCode)
        .filter(models.ShareCode.patient_id == patient_id, models.ShareCode.revoked_at.is_(None))
        .all()
    )
    now = _now()
    for row in existing:
        row.revoked_at = now
    grants = (
        db.query(models.ClinicianAccess)
        .filter(models.ClinicianAccess.patient_id == patient_id, models.ClinicianAccess.revoked_at.is_(None))
        .all()
    )
    for grant in grants:
        grant.revoked_at = now

    code = models.ShareCode(
        patient_id=patient_id,
        code=secrets.token_hex(3).upper(),
        created_at=now,
        expires_at=now + CODE_TTL,
    )
    db.add(code)
    db.flush()
    return code


def revoke_active_code(db: Session, patient_id: str) -> None:
    now = _now()
    rows = (
        db.query(models.ShareCode)
        .filter(models.ShareCode.patient_id == patient_id, models.ShareCode.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        row.revoked_at = now
    grants = (
        db.query(models.ClinicianAccess)
        .filter(models.ClinicianAccess.patient_id == patient_id, models.ClinicianAccess.revoked_at.is_(None))
        .all()
    )
    for grant in grants:
        grant.revoked_at = now


def active_code(db: Session, patient_id: str) -> models.ShareCode | None:
    row = (
        db.query(models.ShareCode)
        .filter(models.ShareCode.patient_id == patient_id, models.ShareCode.revoked_at.is_(None))
        .order_by(models.ShareCode.created_at.desc())
        .first()
    )
    if row is None:
        return None
    if _aware(row.expires_at) <= _now():
        return None
    return row


def grant_access(db: Session, clinician_id: str, patient_id: str, code: str) -> models.ClinicianAccess:
    now = _now()
    share = (
        db.query(models.ShareCode)
        .filter(models.ShareCode.code == code.strip().upper(), models.ShareCode.patient_id == patient_id)
        .one_or_none()
    )
    if share is None:
        raise ValueError("code does not match this patient")
    if share.revoked_at is not None:
        raise ValueError("code has been revoked")
    if _aware(share.expires_at) <= now:
        raise ValueError("code has expired")

    existing = (
        db.query(models.ClinicianAccess)
        .filter(
            models.ClinicianAccess.clinician_id == clinician_id,
            models.ClinicianAccess.patient_id == patient_id,
            models.ClinicianAccess.revoked_at.is_(None),
        )
        .one_or_none()
    )
    if existing:
        return existing

    grant = models.ClinicianAccess(
        clinician_id=clinician_id,
        patient_id=patient_id,
        share_code_id=share.id,
    )
    db.add(grant)
    db.flush()
    return grant


def clinician_patient_ids(db: Session, clinician_id: str) -> list[str]:
    rows = (
        db.query(models.ClinicianAccess)
        .filter(
            models.ClinicianAccess.clinician_id == clinician_id,
            models.ClinicianAccess.revoked_at.is_(None),
        )
        .all()
    )
    return [row.patient_id for row in rows]


def visible_patient_ids(
    db: Session,
    role: str | None,
    actor_patient_id: str | None,
    clinician_id: str | None,
) -> list[str]:
    if role == "patient" and actor_patient_id:
        return [actor_patient_id]
    if role == "clinician" and clinician_id:
        return clinician_patient_ids(db, clinician_id)
    return []


def can_view_patient(db: Session, patient_id: str, role: str | None, actor_patient_id: str | None, clinician_id: str | None) -> bool:
    if role == "patient" and actor_patient_id == patient_id:
        return True
    if role == "clinician" and clinician_id:
        return patient_id in clinician_patient_ids(db, clinician_id)
    return False
