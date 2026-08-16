from app.db.models import Patient
from app.schemas.extracted import CanonicalLabReport, CanonicalPatient, CanonicalPrescription
from app.services.linking.patients import link_patient


def _lab(name, patient_id=None, dob=None, phone=None):
    return CanonicalLabReport(
        patient=CanonicalPatient(name=name, patient_id=patient_id, date_of_birth=dob, phone=phone),
        date="2026-07-12",
        tests=[],
    )


def test_name_and_phone_links(db):
    first = link_patient(db, _lab("Aarav Sharma", "HOSP-1", "1988-03-14", "9876543210"))
    db.commit()
    second = link_patient(db, _lab("Aarav Sharma", "HOSP-9", "1988-03-14", "98765 43210"))
    assert first.patient_id == second.patient_id
    assert second.match_method == "name_and_phone"
    assert not second.needs_review
    assert db.query(Patient).count() == 1
    stored = db.get(Patient, first.patient_id)
    assert stored.external_patient_id == "HOSP-1"


def test_hospital_id_is_not_identity(db):
    first = link_patient(db, _lab("Aarav Sharma", "PAT-1001", "1988-03-14", "1111111111"))
    db.commit()
    second = link_patient(db, _lab("Priya Nair", "PAT-1001", "1992-06-20", "2222222222"))
    assert first.patient_id != second.patient_id
    assert db.query(Patient).count() == 2


def test_name_and_dob_links_without_phone(db):
    first = link_patient(db, _lab("Priya Nair", None, "1992-06-20"))
    db.commit()
    second = link_patient(db, _lab("Priya Nair", None, "1992-06-20"))
    assert first.patient_id == second.patient_id
    assert second.match_method == "name_and_dob"


def test_ambiguous_partial_name_is_not_merged(db):
    first = link_patient(db, _lab("Priya Nair", None, "1992-06-20"))
    db.commit()
    rx = CanonicalPrescription(
        patient=CanonicalPatient(name="P. Nair", patient_id=None, date_of_birth=None),
        date="2026-08-08",
        medications=[],
    )
    second = link_patient(db, rx)
    assert second.needs_review
    assert second.patient_id != first.patient_id
    assert second.match_method in {"ambiguous_partial_name", "ambiguous_name_only", "ambiguous_fuzzy_name"}
    assert db.query(Patient).count() == 2
