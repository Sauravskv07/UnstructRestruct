from __future__ import annotations

import re


TEST_ALIASES = {
    "hb": "hemoglobin",
    "hgb": "hemoglobin",
    "hgb.": "hemoglobin",
    "haemoglobin": "hemoglobin",
    "hemoglobin": "hemoglobin",
    "hba1c": "hba1c",
    "hb a1c": "hba1c",
    "a1c": "hba1c",
    "creatinine": "creatinine",
    "creat": "creatinine",
    "creat.": "creatinine",
    "wbc": "wbc",
    "white blood cell": "wbc",
    "white blood cells": "wbc",
    "tsh": "tsh",
    "glucose": "glucose",
    "fbs": "glucose",
    "fasting glucose": "glucose",
    "platelet": "platelets",
    "platelets": "platelets",
    "plt": "platelets",
    "rbc": "rbc",
    "red blood cell": "rbc",
    "red blood cells": "rbc",
    "ldl": "ldl",
    "hdl": "hdl",
    "cholesterol": "cholesterol",
}

TEST_LABELS = {
    "hemoglobin": "Hemoglobin",
    "hba1c": "HbA1c",
    "creatinine": "Creatinine",
    "wbc": "WBC",
    "tsh": "TSH",
    "glucose": "Glucose",
    "platelets": "Platelets",
    "rbc": "RBC",
    "ldl": "LDL",
    "hdl": "HDL",
    "cholesterol": "Cholesterol",
}

MED_ALIASES = {
    "amoxicillin": "amoxicillin",
    "amoxycillin": "amoxicillin",
    "paracetamol": "paracetamol",
    "acetaminophen": "paracetamol",
    "metformin": "metformin",
    "atorvastatin": "atorvastatin",
    "amlodipine": "amlodipine",
}

MED_LABELS = {
    "amoxicillin": "Amoxicillin",
    "paracetamol": "Paracetamol",
    "metformin": "Metformin",
    "atorvastatin": "Atorvastatin",
    "amlodipine": "Amlodipine",
}

STUDY_ALIASES = {
    "chest x ray": "chest_xray",
    "chest xray": "chest_xray",
    "chest x-ray": "chest_xray",
    "x ray": "chest_xray",
    "xray": "chest_xray",
    "cxr": "chest_xray",
    "chest x ray pa view": "chest_xray",
    "chest x-ray pa view": "chest_xray",
    "mri": "mri",
    "ct": "ct",
    "ct scan": "ct",
    "ultrasound": "ultrasound",
    "usg": "ultrasound",
    "echo": "echo",
    "ecg": "ecg",
    "ekg": "ecg",
}

STUDY_LABELS = {
    "chest_xray": "Chest X-ray",
    "mri": "MRI",
    "ct": "CT",
    "ultrasound": "Ultrasound",
    "echo": "Echo",
    "ecg": "ECG",
}


def _key(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip())


def normalize_test_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = _key(raw)
    if key in TEST_ALIASES:
        return TEST_ALIASES[key]
    compact = key.replace(" ", "")
    if compact in TEST_ALIASES:
        return TEST_ALIASES[compact]
    return key or None


def normalize_medication_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = _key(raw)
    first = key.split(" ")[0] if key else ""
    if first in MED_ALIASES:
        return MED_ALIASES[first]
    if key in MED_ALIASES:
        return MED_ALIASES[key]
    return key or None


def normalize_study_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = _key(raw)
    if key in STUDY_ALIASES:
        return STUDY_ALIASES[key]
    compact = key.replace(" ", "")
    if compact in STUDY_ALIASES:
        return STUDY_ALIASES[compact]
    for alias, canonical in STUDY_ALIASES.items():
        if key.startswith(alias) or alias in key:
            return canonical
    return key.replace(" ", "_") or None


def normalize_person_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = re.sub(r"[^a-zA-Z .]", " ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    cleaned = re.sub(r"\b(mr|mrs|ms|dr|miss)\b\.?", "", cleaned).strip()
    return cleaned or None


def catalog_ids(aliases: dict[str, str]) -> list[str]:
    return sorted(set(aliases.values()))


def human_label(canonical: str, labels: dict[str, str]) -> str:
    if canonical in labels:
        return labels[canonical]
    return canonical.replace("_", " ").title()
