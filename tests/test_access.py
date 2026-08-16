from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.access import ClinicianLoginBody, PatientLoginBody, clinician_login, patient_login
from app.db.models import Clinician, Patient
from app.services.access import active_code, generate_code, grant_access, revoke_active_code, visible_patient_ids
from app.services.timeline import cluster_timeline


def _patient(db) -> Patient:
    patient = Patient(canonical_name="Priya Nair", external_patient_id="PAT-2001", date_of_birth="1992-06-20")
    db.add(patient)
    db.commit()
    return patient


def test_new_code_revokes_old_and_grants(db):
    patient = _patient(db)
    first = generate_code(db, patient.id)
    db.commit()
    grant_access(db, "clin-1", patient.id, first.code)
    db.commit()

    second = generate_code(db, patient.id)
    db.commit()
    db.refresh(first)
    assert first.revoked_at is not None
    assert second.code != first.code
    assert active_code(db, patient.id).code == second.code

    try:
        grant_access(db, "clin-1", patient.id, first.code)
        assert False, "old code should not work"
    except ValueError:
        pass


def test_revoke_blocks_clinician(db):
    patient = _patient(db)
    code = generate_code(db, patient.id)
    db.commit()
    grant_access(db, "clin-1", patient.id, code.code)
    db.commit()
    revoke_active_code(db, patient.id)
    db.commit()
    assert active_code(db, patient.id) is None


def test_expired_code_is_not_active(db):
    patient = _patient(db)
    code = generate_code(db, patient.id)
    code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert active_code(db, patient.id) is None


def test_date_clusters_group_and_order():
    clusters = cluster_timeline(
        [
            {"document_id": "1", "date": "2026-07-12", "document_type": "lab_report", "filename": "a.pdf", "summary": ["hemoglobin: 13.2 g/dL"]},
            {"document_id": "2", "date": "2026-07-12", "document_type": "prescription", "filename": "b.pdf", "summary": ["amoxicillin · 500 mg · 1 tablet · twice daily"]},
            {"document_id": "3", "date": "2026-03-01", "document_type": "diagnostic_report", "filename": "c.pdf", "summary": ["Chest X-ray"]},
            {"document_id": "4", "date": None, "document_type": "lab_report", "filename": "d.pdf", "summary": []},
        ]
    )
    assert clusters[0]["title"] == "2026-07-12"
    assert clusters[0]["document_count"] == 2
    assert "lab report" in clusters[0]["description"]
    assert clusters[1]["title"] == "2026-03-01"
    assert clusters[-1]["title"] == "Undated"


def test_clinician_only_sees_granted_patients(db):
    patient = _patient(db)
    other = Patient(canonical_name="Aarav Sharma", external_patient_id="PAT-1001")
    db.add(other)
    db.commit()
    code = generate_code(db, patient.id)
    db.commit()
    grant_access(db, "doc-internal", patient.id, code.code)
    db.commit()
    assert visible_patient_ids(db, "clinician", None, "doc-internal") == [patient.id]
    assert other.id not in visible_patient_ids(db, "clinician", None, "doc-internal")
    assert visible_patient_ids(db, None, None, None) == []


def test_unknown_patient_login_creates_account(db):
    result = patient_login(PatientLoginBody(patient_id="PAT-3001", password="secret"), db)
    assert result["username"] == "PAT-3001"
    assert result["external_patient_id"] is None
    stored = db.get(Patient, result["patient_id"])
    assert stored is not None
    assert stored.username == "PAT-3001"
    assert stored.external_patient_id is None
    assert stored.password_hash

    again = patient_login(PatientLoginBody(patient_id="PAT-3001", password="secret"), db)
    assert again["patient_id"] == result["patient_id"]

    with pytest.raises(HTTPException) as err:
        patient_login(PatientLoginBody(patient_id="PAT-3001", password="demo"), db)
    assert err.value.status_code == 401


def test_document_created_patient_uses_demo_password(db):
    patient = Patient(canonical_name="Aarav Sharma", external_patient_id="PAT-1001")
    db.add(patient)
    db.commit()

    with pytest.raises(HTTPException):
        patient_login(PatientLoginBody(patient_id="PAT-1001", password="secret"), db)

    result = patient_login(PatientLoginBody(patient_id="PAT-1001", password="demo"), db)
    assert result["patient_id"] == patient.id
    assert result["username"] == "PAT-1001"


def test_new_patient_login_stores_name_and_phone(db):
    result = patient_login(
        PatientLoginBody(username="kajal", password="secret", name="Kajal Virmani", phone="9998887776"),
        db,
    )
    stored = db.get(Patient, result["patient_id"])
    assert stored.canonical_name == "Kajal Virmani"
    assert stored.normalized_phone == "9998887776"
    assert stored.username == "kajal"


def test_unknown_clinician_login_creates_account(db):
    result = clinician_login(ClinicianLoginBody(clinician_id="DOC-2001", password="secret"), db)
    assert result["external_id"] == "DOC-2001"
    stored = db.get(Clinician, result["clinician_id"])
    assert stored is not None
    assert stored.password_hash

    again = clinician_login(ClinicianLoginBody(clinician_id="DOC-2001", password="secret"), db)
    assert again["clinician_id"] == result["clinician_id"]

    with pytest.raises(HTTPException) as err:
        clinician_login(ClinicianLoginBody(clinician_id="DOC-2001", password="demo"), db)
    assert err.value.status_code == 401


def test_seeded_clinician_uses_demo_password(db):
    clinician = Clinician(external_id="DOC-1001", name="Dr. Meera Kapoor")
    db.add(clinician)
    db.commit()

    with pytest.raises(HTTPException):
        clinician_login(ClinicianLoginBody(clinician_id="DOC-1001", password="secret"), db)

    result = clinician_login(ClinicianLoginBody(clinician_id="doc-1001", password="demo"), db)
    assert result["clinician_id"] == clinician.id


def test_medication_timeline_line_includes_dose():
    from types import SimpleNamespace

    from app.api.patients import _medication_line

    line = _medication_line(
        SimpleNamespace(
            canonical_name="amoxicillin",
            raw_name="Amox",
            strength="500 mg",
            dose="1 tablet",
            frequency="twice daily",
            route="oral",
            duration="5 days",
            quantity=None,
            instructions="after food",
        )
    )
    assert line.startswith("amoxicillin")
    assert "500 mg" in line
    assert "1 tablet" in line
    assert "twice daily" in line
    assert "after food" in line
    duplicate = _medication_line(
        SimpleNamespace(
            canonical_name="amoxicillin",
            raw_name="Amoxycillin",
            strength="500 mg",
            dose="1 tablet",
            frequency="twice daily",
            route="oral",
            duration="for 5 days",
            quantity=None,
            instructions="1. Amoxycillin 500 mg 1 tablet oral twice daily for 5 days",
        )
    )
    assert duplicate == "amoxicillin · 500 mg · 1 tablet · twice daily · oral · for 5 days"
    assert "—" not in duplicate
