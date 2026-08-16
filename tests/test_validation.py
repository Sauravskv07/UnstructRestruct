from app.schemas.extracted import (
    CanonicalLabReport,
    CanonicalLabTest,
    CanonicalMedication,
    CanonicalPatient,
    CanonicalPrescription,
    ReferenceRangeExtract,
)
from app.services.validation.validate import validate_lab, validate_prescription


def _lab(*tests: CanonicalLabTest) -> CanonicalLabReport:
    return CanonicalLabReport(patient=CanonicalPatient(name="Aarav"), date="2026-07-12", tests=list(tests))


def test_unparseable_lab_value():
    report = _lab(
        CanonicalLabTest(raw_name="Hb", raw_value="see comments", value=None, unit="g/dL"),
    )
    issues = validate_lab(report)
    assert any(i.code == "unparseable_value" for i in issues)
    assert report.tests[0].validation_status == "validation_failed"


def test_inconsistent_hemoglobin_values():
    report = _lab(
        CanonicalLabTest(raw_name="Haemoglobin", canonical_name="hemoglobin", raw_value="13.2", value=13.2),
        CanonicalLabTest(raw_name="Hemoglobin", canonical_name="hemoglobin", raw_value="8.1", value=8.1),
    )
    issues = validate_lab(report)
    assert any(i.code == "inconsistent_values" for i in issues)


def test_invalid_reference_range():
    report = _lab(
        CanonicalLabTest(
            raw_name="Hb",
            raw_value="13.2",
            value=13.2,
            reference_range=ReferenceRangeExtract(low=17, high=13),
        )
    )
    issues = validate_lab(report)
    assert any(i.code == "invalid_range" for i in issues)


def test_does_not_invent_abnormal_from_range_alone():
    report = _lab(
        CanonicalLabTest(
            raw_name="Hb",
            canonical_name="hemoglobin",
            raw_value="8.1",
            value=8.1,
            reference_range=ReferenceRangeExtract(low=13, high=17),
            abnormal_flag=None,
        )
    )
    issues = validate_lab(report)
    assert not any(i.code == "flag_inconsistent_with_range" for i in issues)


def test_prescription_missing_name():
    rx = CanonicalPrescription(
        patient=CanonicalPatient(name="X"),
        medications=[CanonicalMedication(raw_name=None, dose="1 tablet")],
    )
    issues = validate_prescription(rx)
    assert any(i.code == "missing_name" for i in issues)
