from __future__ import annotations

import re

from app.schemas.extracted import (
    CanonicalDiagnosticReport,
    CanonicalLabReport,
    CanonicalLabTest,
    CanonicalMedication,
    CanonicalPatient,
    CanonicalPrescription,
    DiagnosticReportExtract,
    LabReportExtract,
    PrescriptionExtract,
    Provenance,
)
from app.services.normalization.dates import normalize_date
from app.services.normalization.names import normalize_medication_name, normalize_study_name, normalize_test_name
from app.services.normalization.units import normalize_unit


def normalize_payload(document_id: str, extracted):
    if isinstance(extracted, LabReportExtract):
        return _lab(document_id, extracted)
    if isinstance(extracted, PrescriptionExtract):
        return _rx(document_id, extracted)
    if isinstance(extracted, DiagnosticReportExtract):
        return _dx(document_id, extracted)
    raise TypeError(f"unsupported extract type {type(extracted)}")


def _patient(document_id: str, patient) -> CanonicalPatient:
    return CanonicalPatient(
        name=patient.name,
        phone=patient.phone,
        patient_id=patient.patient_id,
        date_of_birth=normalize_date(patient.date_of_birth),
        provenance=Provenance(
            document_id=document_id,
            page=patient.page,
            source_text=patient.source_text or patient.name,
        ),
    )


def _lab(document_id: str, extracted: LabReportExtract) -> CanonicalLabReport:
    tests = []
    for test in extracted.tests:
        tests.append(
            CanonicalLabTest(
                raw_name=test.raw_name,
                canonical_name=normalize_test_name(test.raw_name),
                raw_value=test.raw_value,
                value=_number(test.raw_value),
                unit=normalize_unit(test.unit),
                reference_range=test.reference_range,
                abnormal_flag=test.abnormal_flag,
                provenance=Provenance(
                    document_id=document_id,
                    page=test.page,
                    source_text=test.source_text,
                ),
                confidence=test.confidence,
            )
        )
    return CanonicalLabReport(
        patient=_patient(document_id, extracted.patient),
        date=normalize_date(extracted.date),
        tests=tests,
    )


def _rx(document_id: str, extracted: PrescriptionExtract) -> CanonicalPrescription:
    meds = []
    for med in extracted.medications:
        meds.append(
            CanonicalMedication(
                raw_name=med.raw_name,
                canonical_name=normalize_medication_name(med.raw_name),
                strength=med.strength,
                dose=med.dose,
                route=med.route,
                frequency=med.frequency,
                duration=med.duration,
                quantity=med.quantity,
                instructions=med.instructions,
                provenance=Provenance(
                    document_id=document_id,
                    page=med.page,
                    source_text=med.source_text,
                ),
                confidence=med.confidence,
            )
        )
    return CanonicalPrescription(
        patient=_patient(document_id, extracted.patient),
        doctor=extracted.doctor,
        date=normalize_date(extracted.date),
        diagnosis=extracted.diagnosis,
        medications=meds,
    )


def _dx(document_id: str, extracted: DiagnosticReportExtract) -> CanonicalDiagnosticReport:
    return CanonicalDiagnosticReport(
        patient=_patient(document_id, extracted.patient),
        date=normalize_date(extracted.date),
        study=extracted.study,
        canonical_study=normalize_study_name(extracted.study),
        findings=extracted.findings,
        impression=extracted.impression,
        provenance=Provenance(
            document_id=document_id,
            page=extracted.page,
            source_text=extracted.source_text,
        ),
        confidence=extracted.confidence,
    )


def _number(raw: str | None) -> float | None:
    if raw is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", raw.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))
