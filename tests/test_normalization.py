from app.services.normalization.dates import normalize_date
from app.services.normalization.names import normalize_medication_name, normalize_study_name, normalize_test_name
from app.services.normalization.units import normalize_unit


def test_date_formats():
    assert normalize_date("12/07/2026") == "2026-07-12"
    assert normalize_date("12-Jul-2026") == "2026-07-12"
    assert normalize_date("July 12, 2026") == "2026-07-12"
    assert normalize_date("14 Mar 1988") == "1988-03-14"
    assert normalize_date("not a date") is None
    assert normalize_date(None) is None


def test_unit_normalization():
    assert normalize_unit("g/dl") == "g/dL"
    assert normalize_unit("g/DL") == "g/dL"
    assert normalize_unit("G/DL") == "g/dL"
    assert normalize_unit("mg/dl") == "mg/dL"


def test_test_name_normalization():
    assert normalize_test_name("Hb") == "hemoglobin"
    assert normalize_test_name("HGB") == "hemoglobin"
    assert normalize_test_name("Hemoglobin") == "hemoglobin"
    assert normalize_test_name("Haemoglobin") == "hemoglobin"
    assert normalize_test_name("HbA1c") == "hba1c"


def test_medication_aliases():
    assert normalize_medication_name("Amoxycillin") == "amoxicillin"
    assert normalize_medication_name("Acetaminophen 650") == "paracetamol"


def test_study_name_normalization():
    assert normalize_study_name("Chest X-ray PA view") == "chest_xray"
    assert normalize_study_name("CXR") == "chest_xray"
    assert normalize_study_name("MRI") == "mri"
