from datetime import datetime

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    id: str
    filename: str
    document_type: str | None
    status: str
    patient_id: str | None
    patient_name: str | None = None
    document_date: str | None
    needs_review: bool
    page_count: int
    used_ocr: bool
    created_at: datetime


class PatientSummary(BaseModel):
    id: str
    canonical_name: str | None
    external_patient_id: str | None
    date_of_birth: str | None
    needs_review: bool
    document_count: int
