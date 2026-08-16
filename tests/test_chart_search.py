from app.api.patients import (
    get_patient,
    patient_catalog,
    patient_diagnostics,
    patient_lab_results,
    patient_medications,
)
from app.db.models import DiagnosticReport, Document, LabResult, Medication, Patient
from app.services.vocab import LAB, observe


def _chart(db):
    patient = Patient(canonical_name="Aarav Sharma", username="aarav")
    db.add(patient)
    db.flush()
    lab_doc = Document(
        filename="lab.pdf",
        stored_path="lab.pdf",
        status="COMPLETED",
        patient_id=patient.id,
        document_type="lab_report",
        document_date="2026-07-12",
    )
    rx_doc = Document(
        filename="rx.pdf",
        stored_path="rx.pdf",
        status="COMPLETED",
        patient_id=patient.id,
        document_type="prescription",
        document_date="2026-08-08",
    )
    dx_doc = Document(
        filename="dx.pdf",
        stored_path="dx.pdf",
        status="COMPLETED",
        patient_id=patient.id,
        document_type="diagnostic_report",
        document_date="2026-03-01",
    )
    pending = Document(
        filename="pending.pdf",
        stored_path="pending.pdf",
        status="PENDING_CONFIRMATION",
        patient_id=patient.id,
        document_type="lab_report",
        document_date="2026-09-01",
    )
    db.add_all([lab_doc, rx_doc, dx_doc, pending])
    db.flush()
    db.add(
        LabResult(
            document_id=lab_doc.id,
            patient_id=None,
            canonical_name="hemoglobin",
            raw_name="Hb",
            value=13.2,
            unit="g/dL",
            test_date="2026-07-12",
        )
    )
    db.add(
        Medication(
            document_id=rx_doc.id,
            patient_id=patient.id,
            canonical_name="amoxicillin",
            raw_name="Amoxycillin",
            strength="500 mg",
            dose="1 tablet",
            frequency="twice daily",
            prescribed_date="2026-08-08",
        )
    )
    db.add(
        DiagnosticReport(
            document_id=dx_doc.id,
            patient_id=patient.id,
            study="Chest X-ray PA view",
            canonical_study="chest_xray",
            impression="No acute abnormality",
            report_date="2026-03-01",
        )
    )
    db.commit()
    return patient


def test_empty_catalog_is_chart_only(db):
    patient = _chart(db)
    catalog = patient_catalog(patient.id, None, "", db, "patient", patient.id, None)
    labs = {item["id"]: item for item in catalog["lab_tests"]}
    assert labs["hemoglobin"]["in_chart"] is True
    assert "creatinine" not in labs
    meds = {item["id"]: item for item in catalog["medications"]}
    assert list(meds) == ["amoxicillin"]
    studies = {item["id"]: item for item in catalog["diagnostics"]}
    assert list(studies) == ["chest_xray"]


def test_fuzzy_search_uses_global_vocab(db):
    patient = _chart(db)
    other = Patient(canonical_name="Priya Nair", username="priya")
    db.add(other)
    db.flush()
    other_doc = Document(
        filename="other-lab.pdf",
        stored_path="other-lab.pdf",
        status="COMPLETED",
        patient_id=other.id,
        document_type="lab_report",
    )
    db.add(other_doc)
    db.flush()
    db.add(LabResult(document_id=other_doc.id, patient_id=other.id, canonical_name="lipase", raw_name="Lipase"))
    observe(db, LAB, "lipase", "Lipase")
    db.commit()

    hemo = patient_catalog(patient.id, "lab_test", "hemo", db, "patient", patient.id, None)
    assert hemo[0]["id"] == "hemoglobin"
    assert hemo[0]["in_chart"] is True

    creat = patient_catalog(patient.id, "lab_test", "creat", db, "patient", patient.id, None)
    ids = [item["id"] for item in creat]
    assert "creatinine" in ids
    assert any(item["id"] == "creatinine" and item["in_chart"] is False for item in creat)

    lipase = patient_catalog(patient.id, "lab_test", "lipas", db, "patient", patient.id, None)
    assert lipase[0]["id"] == "lipase"
    assert lipase[0]["in_chart"] is False

    amox = patient_catalog(patient.id, "medication", "amoxi", db, "patient", patient.id, None)
    assert amox[0]["id"] == "amoxicillin"

    cxr = patient_catalog(patient.id, "diagnostic", "xray", db, "patient", patient.id, None)
    assert cxr[0]["id"] == "chest_xray"
    assert cxr[0]["in_chart"] is True


def test_diagnostic_in_chart_from_raw_study(db):
    patient = Patient(canonical_name="Aarav Sharma", username="aarav")
    db.add(patient)
    db.flush()
    doc = Document(
        filename="dx.pdf",
        stored_path="dx.pdf",
        status="COMPLETED",
        patient_id=patient.id,
        document_type="diagnostic_report",
    )
    db.add(doc)
    db.flush()
    db.add(
        DiagnosticReport(
            document_id=doc.id,
            patient_id=None,
            study="Chest X-ray PA view",
            canonical_study=None,
        )
    )
    db.commit()
    hits = patient_catalog(patient.id, "diagnostic", "chest xray", db, "patient", patient.id, None)
    assert hits[0]["id"] == "chest_xray"
    assert hits[0]["in_chart"] is True
    assert all(item["id"] != "chest x ray pa view" for item in hits)


def test_duplicate_study_term_collapses_to_canonical(db):
    from app.db.models import VocabularyTerm
    from app.services.vocab import DX, observe

    patient = _chart(db)
    observe(db, DX, None, "Chest X-ray PA view")
    db.add(VocabularyTerm(kind=DX, canonical="chest x ray pa view", label="Chest X Ray Pa View"))
    db.commit()
    hits = patient_catalog(patient.id, "diagnostic", "chest xray", db, "patient", patient.id, None)
    assert hits[0]["id"] == "chest_xray"
    assert hits[0]["in_chart"] is True


def test_date_range_filters_timeline(db):
    patient = _chart(db)
    full = get_patient(patient.id, None, None, db, "patient", patient.id, None)
    assert len(full["timeline"]) == 3
    summer = get_patient(patient.id, "2026-06-01", "2026-08-31", db, "patient", patient.id, None)
    dates = {item["date"] for item in summer["timeline"]}
    assert dates == {"2026-07-12", "2026-08-08"}


def test_lab_med_diagnostic_filters(db):
    patient = _chart(db)
    labs = patient_lab_results(patient.id, "hemoglobin", db, "patient", patient.id, None)
    assert len(labs) == 1
    by_alias = patient_lab_results(patient.id, "Hb", db, "patient", patient.id, None)
    assert len(by_alias) == 1
    assert labs[0]["value"] == 13.2
    assert labs[0]["document_id"]
    empty = patient_lab_results(patient.id, "creatinine", db, "patient", patient.id, None)
    assert empty == []
    meds = patient_medications(patient.id, "amoxicillin", db, "patient", patient.id, None)
    assert len(meds) == 1
    assert "500 mg" in meds[0]["line"]
    dx = patient_diagnostics(patient.id, "chest_xray", db, "patient", patient.id, None)
    assert len(dx) == 1
    assert dx[0]["canonical_study"] == "chest_xray"
