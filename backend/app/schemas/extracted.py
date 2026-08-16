from typing import Literal

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    document_id: str | None = None
    page: int | None = None
    source_text: str | None = None
    bbox: tuple[float, float, float, float] | None = None


class PatientExtract(BaseModel):
    name: str | None = None
    phone: str | None = None
    patient_id: str | None = None
    date_of_birth: str | None = None
    page: int | None = None
    source_text: str | None = None


class DoctorExtract(BaseModel):
    name: str | None = None
    credentials: str | None = None
    page: int | None = None
    source_text: str | None = None


class ReferenceRangeExtract(BaseModel):
    low: float | None = None
    high: float | None = None
    raw: str | None = None


class LabTestExtract(BaseModel):
    raw_name: str | None = None
    raw_value: str | None = None
    unit: str | None = None
    reference_range: ReferenceRangeExtract | None = None
    abnormal_flag: str | None = None
    page: int | None = None
    source_text: str | None = None
    confidence: float | None = None


class MedicationExtract(BaseModel):
    raw_name: str | None = None
    strength: str | None = None
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    quantity: str | None = None
    instructions: str | None = None
    page: int | None = None
    source_text: str | None = None
    confidence: float | None = None


class ClassificationResult(BaseModel):
    document_type: Literal["lab_report", "prescription", "diagnostic_report", "unknown"]
    confidence: float
    reason: str | None = None


class LabReportExtract(BaseModel):
    document_type: Literal["lab_report"] = "lab_report"
    patient: PatientExtract = Field(default_factory=PatientExtract)
    date: str | None = None
    date_page: int | None = None
    date_source_text: str | None = None
    tests: list[LabTestExtract] = Field(default_factory=list)


class PrescriptionExtract(BaseModel):
    document_type: Literal["prescription"] = "prescription"
    patient: PatientExtract = Field(default_factory=PatientExtract)
    doctor: DoctorExtract = Field(default_factory=DoctorExtract)
    date: str | None = None
    date_page: int | None = None
    date_source_text: str | None = None
    diagnosis: str | None = None
    medications: list[MedicationExtract] = Field(default_factory=list)


class DiagnosticReportExtract(BaseModel):
    document_type: Literal["diagnostic_report"] = "diagnostic_report"
    patient: PatientExtract = Field(default_factory=PatientExtract)
    date: str | None = None
    date_page: int | None = None
    date_source_text: str | None = None
    study: str | None = None
    findings: str | None = None
    impression: str | None = None
    page: int | None = None
    source_text: str | None = None
    confidence: float | None = None


class CanonicalLabTest(BaseModel):
    raw_name: str | None = None
    canonical_name: str | None = None
    raw_value: str | None = None
    value: float | None = None
    unit: str | None = None
    reference_range: ReferenceRangeExtract | None = None
    abnormal_flag: str | None = None
    provenance: Provenance | None = None
    confidence: float | None = None
    validation_status: str = "ok"


class CanonicalMedication(BaseModel):
    raw_name: str | None = None
    canonical_name: str | None = None
    strength: str | None = None
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    quantity: str | None = None
    instructions: str | None = None
    provenance: Provenance | None = None
    confidence: float | None = None
    validation_status: str = "ok"


class CanonicalPatient(BaseModel):
    name: str | None = None
    phone: str | None = None
    patient_id: str | None = None
    date_of_birth: str | None = None
    provenance: Provenance | None = None


class CanonicalLabReport(BaseModel):
    document_type: Literal["lab_report"] = "lab_report"
    patient: CanonicalPatient
    date: str | None = None
    tests: list[CanonicalLabTest] = Field(default_factory=list)


class CanonicalPrescription(BaseModel):
    document_type: Literal["prescription"] = "prescription"
    patient: CanonicalPatient
    doctor: DoctorExtract = Field(default_factory=DoctorExtract)
    date: str | None = None
    diagnosis: str | None = None
    medications: list[CanonicalMedication] = Field(default_factory=list)


class CanonicalDiagnosticReport(BaseModel):
    document_type: Literal["diagnostic_report"] = "diagnostic_report"
    patient: CanonicalPatient
    date: str | None = None
    study: str | None = None
    canonical_study: str | None = None
    findings: str | None = None
    impression: str | None = None
    provenance: Provenance | None = None
    confidence: float | None = None
    validation_status: str = "ok"
