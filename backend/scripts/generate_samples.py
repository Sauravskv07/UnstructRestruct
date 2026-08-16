"""Generate synthetic medical PDFs for the assignment. No real patient data."""

from __future__ import annotations

from pathlib import Path

import fitz

from app.config import REPO_ROOT


OUT = REPO_ROOT / "sample_documents"


def _pdf(path: Path, lines: list[tuple[str, float]]) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 72
    for text, size in lines:
        page.insert_text((72, y), text, fontsize=size, fontname="helv")
        y += size + 10
        if y > 780:
            page = doc.new_page(width=595, height=842)
            y = 72
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def _to_scanned(src: Path, dest: Path) -> None:
    src_doc = fitz.open(src)
    out = fitz.open()
    for page in src_doc:
        pix = page.get_pixmap(dpi=110)
        jpeg = pix.tobytes("jpeg")
        new_page = out.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=jpeg)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest)
    out.close()
    src_doc.close()


def generate(out_dir: Path | None = None) -> Path:
    dest = out_dir or OUT
    dest.mkdir(parents=True, exist_ok=True)

    _pdf(
        dest / "01_clean_lab_aarav.pdf",
        [
            ("CITY LAB SERVICES", 16),
            ("Laboratory Report", 14),
            ("Patient Name: Aarav Sharma", 11),
            ("Patient ID: PAT-1001", 11),
            ("DOB: 14 Mar 1988", 11),
            ("Date: 12-Jul-2026", 11),
            ("Test Name            Result     Unit     Reference", 11),
            ("Haemoglobin          13.2       g/DL     13.0 - 17.0", 11),
            ("Creatinine           0.9        mg/dl    0.7 - 1.3", 11),
            ("WBC                  7.1        10^3/uL  4.0 - 11.0", 11),
        ],
    )

    clean = dest / "01_clean_lab_aarav.pdf"
    _to_scanned(clean, dest / "02_scanned_lab_aarav.pdf")

    _pdf(
        dest / "03_prescription_aarav.pdf",
        [
            ("Dr. Meera Kapoor, MD", 14),
            ("Prescription", 16),
            ("Patient Name: Aarav Sharma", 11),
            ("Patient ID: PAT-1001", 11),
            ("DOB: 03/14/1988", 11),
            ("Date: July 20, 2026", 11),
            ("Diagnosis: Community acquired pneumonia", 11),
            ("1. Amoxycillin 500 mg 1 tablet oral twice daily for 5 days", 11),
            ("2. Paracetamol 650 mg 1 tablet oral as needed", 11),
        ],
    )

    _pdf(
        dest / "04_messy_lab.pdf",
        [
            ("lab rpt / walk-in", 12),
            ("pt: Aarav Sharma   id PAT-1001", 11),
            ("dob 14/03/1988", 11),
            ("dt: 12/07/2026", 11),
            ("Hb 13.2 g/dl (13-17)", 11),
            ("creat. : 0.9 mg/DL", 11),
            ("HGB also written in header notes", 11),
        ],
    )

    _pdf(
        dest / "05_missing_fields_rx.pdf",
        [
            ("Prescription", 16),
            ("Patient Name: Unknown Walk-in", 11),
            ("Date: 2026-08-01", 11),
            ("1. Metformin 500 mg", 11),
        ],
    )

    _pdf(
        dest / "06_inconsistent_lab.pdf",
        [
            ("Laboratory Report", 14),
            ("Patient Name: Aarav Sharma", 11),
            ("Patient ID: PAT-1001", 11),
            ("DOB: 1988-03-14", 11),
            ("Date: 15 Jul 2026", 11),
            ("Haemoglobin          13.2       g/dL     13.0 - 17.0", 11),
            ("Hemoglobin           8.1        g/dL     13.0 - 17.0", 11),
        ],
    )

    _pdf(
        dest / "07_lab_priya.pdf",
        [
            ("Sunrise Diagnostics", 14),
            ("Laboratory Report", 14),
            ("Patient Name: Priya Nair", 11),
            ("DOB: 20 June 1992", 11),
            ("Date: 01 Aug 2026", 11),
            ("HbA1c                7.8", 11),
        ],
    )

    _pdf(
        dest / "08_rx_p_nair.pdf",
        [
            ("Prescription", 16),
            ("Patient Name: P. Nair", 11),
            ("Date: 08/08/2026", 11),
            ("Doctor: Dr. Iyer", 11),
            ("1. Atorvastatin 10 mg 1 tablet oral once daily for 30 days", 11),
        ],
    )

    _pdf(
        dest / "09_diagnostic_aarav.pdf",
        [
            ("Radiology Department", 14),
            ("Diagnostic Report", 14),
            ("Patient Name: Aarav Sharma", 11),
            ("Patient ID: PAT-1001", 11),
            ("DOB: 14 Mar 1988", 11),
            ("Study Date: 01 Mar 2026", 11),
            ("Study: Chest X-ray PA view", 11),
            ("Findings: Lungs are clear. No focal consolidation. Heart size is normal.", 11),
            ("Impression: No acute cardiopulmonary abnormality.", 11),
        ],
    )

    readme = dest / "README.md"
    readme.write_text(
        """# Synthetic sample documents

All documents are fictional. Do not use real patient data.

| File | Purpose |
| --- | --- |
| 01_clean_lab_aarav.pdf | Clean text-layer lab report, patient PAT-1001 |
| 02_scanned_lab_aarav.pdf | Same lab as image-only PDF (OCR path) |
| 03_prescription_aarav.pdf | Prescription for the same patient |
| 04_messy_lab.pdf | Messy labels/units for the same patient |
| 05_missing_fields_rx.pdf | Prescription with missing identifiers/instructions |
| 06_inconsistent_lab.pdf | Two conflicting hemoglobin values |
| 07_lab_priya.pdf | Priya Nair, DOB present, no patient ID, HbA1c without unit |
| 08_rx_p_nair.pdf | P. Nair, no DOB/ID — ambiguous match vs Priya |
| 09_diagnostic_aarav.pdf | Diagnostic report for PAT-1001 |
""",
        encoding="utf-8",
    )
    return dest


if __name__ == "__main__":
    generate()
    print(f"wrote samples to {OUT}")
