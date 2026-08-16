from __future__ import annotations

from dataclasses import dataclass

from app.schemas.extracted import (
    CanonicalDiagnosticReport,
    CanonicalLabReport,
    CanonicalPrescription,
)


@dataclass
class Issue:
    entity_type: str
    field: str | None
    code: str
    message: str
    severity: str = "error"


def validate_canonical(canonical) -> list[Issue]:
    if isinstance(canonical, CanonicalLabReport):
        return validate_lab(canonical)
    if isinstance(canonical, CanonicalPrescription):
        return validate_prescription(canonical)
    if isinstance(canonical, CanonicalDiagnosticReport):
        return validate_diagnostic(canonical)
    return [Issue("document", None, "unknown_type", "unsupported document type")]


def validate_lab(report: CanonicalLabReport) -> list[Issue]:
    issues: list[Issue] = []
    if not report.tests:
        issues.append(Issue("lab_report", "tests", "missing_tests", "no lab tests extracted", "warning"))
    seen: dict[str, float] = {}
    for test in report.tests:
        status = "ok"
        if test.raw_name and test.value is None and test.raw_value:
            issues.append(
                Issue("lab_result", "value", "unparseable_value", f"{test.raw_name}: value {test.raw_value!r} is not numeric")
            )
            status = "validation_failed"
        ref = test.reference_range
        if ref and ref.low is not None and ref.high is not None and ref.low > ref.high:
            issues.append(
                Issue("lab_result", "reference_range", "invalid_range", f"{test.raw_name}: reference low > high")
            )
            status = "validation_failed"
        if test.canonical_name and test.value is not None:
            prior = seen.get(test.canonical_name)
            if prior is not None and abs(prior - test.value) > 1e-6:
                issues.append(
                    Issue(
                        "lab_result",
                        "value",
                        "inconsistent_values",
                        f"{test.canonical_name}: conflicting values {prior} and {test.value} in the same document",
                    )
                )
                status = "validation_failed"
            seen[test.canonical_name] = test.value
        if (
            test.value is not None
            and ref
            and ref.low is not None
            and ref.high is not None
            and test.abnormal_flag
            and test.abnormal_flag.lower() in {"n", "normal"}
            and (test.value < ref.low or test.value > ref.high)
        ):
            issues.append(
                Issue(
                    "lab_result",
                    "abnormal_flag",
                    "flag_inconsistent_with_range",
                    f"{test.raw_name}: marked normal but value {test.value} is outside stated range",
                )
            )
            status = "validation_failed"
        test.validation_status = status
    return issues


def validate_prescription(rx: CanonicalPrescription) -> list[Issue]:
    issues: list[Issue] = []
    if not rx.medications:
        issues.append(Issue("prescription", "medications", "missing_medications", "no medications extracted", "warning"))
    for med in rx.medications:
        status = "ok"
        if not med.raw_name:
            issues.append(Issue("medication", "raw_name", "missing_name", "medication row has no name"))
            status = "validation_failed"
        if med.dose and not med.raw_name:
            issues.append(Issue("medication", "dose", "dose_without_name", "dose present without medication name"))
            status = "validation_failed"
        freq = (med.frequency or "").lower()
        if "once" in freq and "twice" in freq:
            issues.append(
                Issue("medication", "frequency", "inconsistent_frequency", f"{med.raw_name}: conflicting frequency text")
            )
            status = "validation_failed"
        med.validation_status = status
    return issues


def validate_diagnostic(report: CanonicalDiagnosticReport) -> list[Issue]:
    issues: list[Issue] = []
    if not report.study and not report.findings and not report.impression:
        issues.append(
            Issue("diagnostic_report", None, "empty_report", "no study, findings, or impression extracted")
        )
        report.validation_status = "validation_failed"
    else:
        report.validation_status = "ok"
    return issues
