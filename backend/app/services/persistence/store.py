from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db import models
from app.schemas.extracted import (
    CanonicalDiagnosticReport,
    CanonicalLabReport,
    CanonicalPrescription,
)
from app.services.linking.patients import LinkResult
from app.services.validation.validate import Issue
from app.services.vocab import DX, LAB, MED, observe


def persist_canonical(
    db: Session,
    doc: models.Document,
    canonical,
    issues: list[Issue],
    link: LinkResult,
) -> None:
    doc.extracted_json = canonical.model_dump_json()
    doc.document_date = canonical.date
    doc.patient_id = link.patient_id

    doc.lab_results.clear()
    doc.medications.clear()
    if doc.diagnostic_report is not None:
        db.delete(doc.diagnostic_report)
        doc.diagnostic_report = None
    doc.validation_errors.clear()
    doc.links.clear()
    db.flush()

    if isinstance(canonical, CanonicalLabReport):
        for test in canonical.tests:
            doc.lab_results.append(
                models.LabResult(
                    document_id=doc.id,
                    patient_id=link.patient_id,
                    test_date=canonical.date,
                    raw_name=test.raw_name,
                    canonical_name=test.canonical_name,
                    raw_value=test.raw_value,
                    value=test.value,
                    unit=test.unit,
                    reference_low=test.reference_range.low if test.reference_range else None,
                    reference_high=test.reference_range.high if test.reference_range else None,
                    abnormal_flag=test.abnormal_flag,
                    provenance_json=test.provenance.model_dump_json() if test.provenance else None,
                    confidence=test.confidence,
                    validation_status=test.validation_status,
                )
            )
            observe(db, LAB, test.canonical_name, test.raw_name)
    elif isinstance(canonical, CanonicalPrescription):
        for med in canonical.medications:
            doc.medications.append(
                models.Medication(
                    document_id=doc.id,
                    patient_id=link.patient_id,
                    prescribed_date=canonical.date,
                    raw_name=med.raw_name,
                    canonical_name=med.canonical_name,
                    strength=med.strength,
                    dose=med.dose,
                    route=med.route,
                    frequency=med.frequency,
                    duration=med.duration,
                    quantity=med.quantity,
                    instructions=med.instructions,
                    diagnosis=canonical.diagnosis,
                    provenance_json=med.provenance.model_dump_json() if med.provenance else None,
                    confidence=med.confidence,
                    validation_status=med.validation_status,
                )
            )
            observe(db, MED, med.canonical_name, med.raw_name)
    elif isinstance(canonical, CanonicalDiagnosticReport):
        doc.diagnostic_report = models.DiagnosticReport(
            document_id=doc.id,
            patient_id=link.patient_id,
            report_date=canonical.date,
            study=canonical.study,
            canonical_study=canonical.canonical_study,
            findings=canonical.findings,
            impression=canonical.impression,
            provenance_json=canonical.provenance.model_dump_json() if canonical.provenance else None,
            confidence=canonical.confidence,
            validation_status=canonical.validation_status,
        )
        observe(db, DX, canonical.canonical_study, canonical.study)

    for issue in issues:
        doc.validation_errors.append(
            models.ValidationError(
                document_id=doc.id,
                entity_type=issue.entity_type,
                field=issue.field,
                code=issue.code,
                message=issue.message,
                severity=issue.severity,
            )
        )

    doc.links.append(
        models.DocumentLink(
            document_id=doc.id,
            patient_id=link.patient_id,
            match_method=link.match_method,
            match_reason=link.match_reason,
            confidence=link.confidence,
            needs_review=link.needs_review,
            candidate_patient_ids=json.dumps(link.candidate_patient_ids),
        )
    )
    db.flush()
