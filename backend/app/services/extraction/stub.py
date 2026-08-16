from __future__ import annotations

import re

from app.schemas.extracted import (
    DiagnosticReportExtract,
    DoctorExtract,
    LabReportExtract,
    LabTestExtract,
    MedicationExtract,
    PatientExtract,
    PrescriptionExtract,
    ReferenceRangeExtract,
)
from app.schemas.ir import DocumentIR


PATIENT_NAME = re.compile(
    r"(?:Patient(?:\s+Name)?|pt)\s*[:\-]\s*([A-Za-z .]+)", re.I
)
PATIENT_ID = re.compile(
    r"(?:Patient\s*ID|ID|MRN|id)\s*[:\-]?\s*(PAT-[A-Za-z0-9\-]+|[A-Za-z0-9\-]{5,})",
    re.I,
)
PHONE = re.compile(
    r"(?:Phone|Mobile|Mob|Tel|Telephone)\s*[:\-]?\s*(\+?\d[\d\s\-()]{7,}\d)",
    re.I,
)
DOB = re.compile(r"(?:DOB|Date of Birth|dob)\s*[:\-]?\s*([0-9A-Za-z ,/\-]+)", re.I)
DATE = re.compile(
    r"(?:Study Date|Report Date|Date|dt)\s*[:\-]\s*([0-9A-Za-z ,/\-]+)", re.I
)
DOCTOR = re.compile(r"(?:Doctor|Physician|Prescriber)\s*[:\-]\s*([A-Za-z .,\-]+)", re.I)
DIAGNOSIS = re.compile(r"Diagnosis\s*[:\-]\s*(.+)", re.I)
STUDY = re.compile(r"Study\s*[:\-]\s*(.+)", re.I)
FINDINGS = re.compile(r"Findings\s*[:\-]\s*(.+)", re.I | re.S)
IMPRESSION = re.compile(r"Impression\s*[:\-]\s*(.+)", re.I | re.S)

LAB_ROW = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9 ./\-]+?)\s*[:\-]?\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>[A-Za-z/%µμ]+(?:/[A-Za-z]+))?\s*"
    r"(?:\((?P<paren_range>\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?)\))?\s*"
    r"(?P<range>\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?)?",
    re.I,
)

MED_LINE = re.compile(
    r"(?:^\s*(?:\d+[.)]\s*)?(?P<name>[A-Za-z][A-Za-z0-9\- ]+?)\s+"
    r"(?P<strength>\d+\s*mg|\d+\s*mcg)?\s*"
    r"(?P<dose>(?:1 tablet|1 cap|one tablet)[^,\n]*)?,?\s*"
    r"(?P<freq>(?:once daily|twice daily|bid|tid|od|bd|hs)[^,\n]*)?,?\s*"
    r"(?P<dur>(?:for\s+\d+\s+days|x\s*\d+\s*days|\d+\s+days)?)?)",
    re.I | re.M,
)


def extract_with_stub(ir: DocumentIR, document_type: str):
    text = ir.combined_text()
    patient = _patient(text)
    if document_type == "lab_report":
        return LabReportExtract(
            patient=patient,
            date=_first(DATE, text),
            date_page=_page_for(ir, _first(DATE, text)),
            date_source_text=_first(DATE, text),
            tests=_tests(ir),
        )
    if document_type == "prescription":
        return PrescriptionExtract(
            patient=patient,
            doctor=DoctorExtract(name=_first(DOCTOR, text), source_text=_first(DOCTOR, text)),
            date=_first(DATE, text),
            diagnosis=_first(DIAGNOSIS, text),
            medications=_meds(ir),
        )
    findings = _section(FINDINGS, text)
    impression = _section(IMPRESSION, text)
    return DiagnosticReportExtract(
        patient=patient,
        date=_first(DATE, text),
        study=_first(STUDY, text),
        findings=findings,
        impression=impression,
        page=1,
        source_text=(findings or impression or "")[:180],
        confidence=0.7,
    )


def _patient(text: str) -> PatientExtract:
    name = _first(PATIENT_NAME, text)
    return PatientExtract(
        name=name.strip() if name else None,
        phone=_first(PHONE, text),
        patient_id=_first(PATIENT_ID, text),
        date_of_birth=_first(DOB, text),
        page=1,
        source_text=name,
    )


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip()
    value = value.split("\n")[0].strip(" .")
    return value or None


def _section(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip()
    for stop in ("Impression", "Patient", "Date"):
        value = re.split(rf"\n{stop}\b", value, maxsplit=1)[0]
    return value.strip() or None


def _tests(ir: DocumentIR) -> list[LabTestExtract]:
    tests: list[LabTestExtract] = []
    skip = {"patient", "date", "report", "lab", "reference", "name", "value", "unit"}
    for page in ir.pages:
        for line in page.text.splitlines():
            match = LAB_ROW.search(line)
            if not match:
                continue
            name = match.group("name").strip()
            if name.lower() in skip or len(name) < 2:
                continue
            if name.lower().startswith("patient"):
                continue
            raw_range = match.group("paren_range") or match.group("range")
            ref = None
            if raw_range:
                nums = re.findall(r"\d+(?:\.\d+)?", raw_range)
                if len(nums) == 2:
                    ref = ReferenceRangeExtract(low=float(nums[0]), high=float(nums[1]), raw=raw_range)
            tests.append(
                LabTestExtract(
                    raw_name=name,
                    raw_value=match.group("value"),
                    unit=match.group("unit"),
                    reference_range=ref,
                    page=page.page_number,
                    source_text=line.strip(),
                    confidence=0.75,
                )
            )
    return tests


def _meds(ir: DocumentIR) -> list[MedicationExtract]:
    meds: list[MedicationExtract] = []
    for page in ir.pages:
        for line in page.text.splitlines():
            if not re.search(r"\b(mg|tablet|tab|capsule|syrup)\b", line, re.I):
                continue
            if re.search(r"patient|doctor|diagnosis|date", line, re.I):
                continue
            name_match = re.match(r"\s*(?:\d+[.)]\s*)?([A-Za-z][A-Za-z0-9\- ]+)", line)
            if not name_match:
                continue
            strength = re.search(r"(\d+\s*(?:mg|mcg|iu))", line, re.I)
            freq = re.search(r"(once daily|twice daily|bid|tid|od|bd|hs|at night)", line, re.I)
            dur = re.search(r"(for\s+\d+\s+days|\d+\s+days)", line, re.I)
            route = re.search(r"(oral|po|iv|im|topical)", line, re.I)
            meds.append(
                MedicationExtract(
                    raw_name=name_match.group(1).strip(),
                    strength=strength.group(1) if strength else None,
                    dose="1 tablet" if re.search(r"tablet", line, re.I) else None,
                    route=route.group(1) if route else None,
                    frequency=freq.group(1) if freq else None,
                    duration=dur.group(1) if dur else None,
                    instructions=line.strip(),
                    page=page.page_number,
                    source_text=line.strip(),
                    confidence=0.7,
                )
            )
    return meds


def _page_for(ir: DocumentIR, snippet: str | None) -> int | None:
    if not snippet:
        return None
    for page in ir.pages:
        if snippet in page.text:
            return page.page_number
    return 1
