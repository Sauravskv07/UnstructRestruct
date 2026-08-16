import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    canonical_name: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_phone: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    external_patient_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(String, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    documents = relationship("Document", back_populates="patient")


class Clinician(Base):
    __tablename__ = "clinicians"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    external_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String)
    media_type: Mapped[str] = mapped_column(String, default="pdf")
    document_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    has_native_text: Mapped[bool] = mapped_column(Boolean, default=False)
    used_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    document_date: Mapped[str | None] = mapped_column(String, nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ir_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    patient = relationship("Patient", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="document", cascade="all, delete-orphan")
    medications = relationship("Medication", back_populates="document", cascade="all, delete-orphan")
    diagnostic_report = relationship(
        "DiagnosticReport", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    validation_errors = relationship(
        "ValidationError", back_populates="document", cascade="all, delete-orphan"
    )
    links = relationship("DocumentLink", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    blocks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)

    document = relationship("Document", back_populates="pages")


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    test_date: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_name: Mapped[str | None] = mapped_column(String, nullable=True)
    canonical_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    raw_value: Mapped[str | None] = mapped_column(String, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    abnormal_flag: Mapped[str | None] = mapped_column(String, nullable=True)
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, default="ok")

    document = relationship("Document", back_populates="lab_results")


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    prescribed_date: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_name: Mapped[str | None] = mapped_column(String, nullable=True)
    canonical_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    strength: Mapped[str | None] = mapped_column(String, nullable=True)
    dose: Mapped[str | None] = mapped_column(String, nullable=True)
    route: Mapped[str | None] = mapped_column(String, nullable=True)
    frequency: Mapped[str | None] = mapped_column(String, nullable=True)
    duration: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[str | None] = mapped_column(String, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, default="ok")

    document = relationship("Document", back_populates="medications")


class DiagnosticReport(Base):
    __tablename__ = "diagnostic_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    report_date: Mapped[str | None] = mapped_column(String, nullable=True)
    study: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_study: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, default="ok")

    document = relationship("Document", back_populates="diagnostic_report")


class DocumentLink(Base):
    __tablename__ = "document_links"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    match_method: Mapped[str] = mapped_column(String)
    match_reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    candidate_patient_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    document = relationship("Document", back_populates="links")


class ValidationError(Base):
    __tablename__ = "validation_errors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    entity_type: Mapped[str] = mapped_column(String)
    field: Mapped[str | None] = mapped_column(String, nullable=True)
    code: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String, default="error")

    document = relationship("Document", back_populates="validation_errors")


class VocabularyTerm(Base):
    __tablename__ = "vocabulary_terms"
    __table_args__ = (UniqueConstraint("kind", "canonical", name="uq_vocab_kind_canonical"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String, index=True)
    canonical: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String)


class VocabularyAlias(Base):
    __tablename__ = "vocabulary_aliases"
    __table_args__ = (UniqueConstraint("kind", "alias_key", name="uq_vocab_kind_alias"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String, index=True)
    alias_key: Mapped[str] = mapped_column(String)
    canonical: Mapped[str] = mapped_column(String, index=True)


class ShareCode(Base):
    __tablename__ = "share_codes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ClinicianAccess(Base):
    __tablename__ = "clinician_access"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    clinician_id: Mapped[str] = mapped_column(String, index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    share_code_id: Mapped[str | None] = mapped_column(ForeignKey("share_codes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
