from __future__ import annotations

import re


UNIT_MAP = {
    "g/dl": "g/dL",
    "gm/dl": "g/dL",
    "gm/dL": "g/dL",
    "g/dL": "g/dL",
    "mg/dl": "mg/dL",
    "mg/dL": "mg/dL",
    "mmol/l": "mmol/L",
    "mmol/L": "mmol/L",
    "%": "%",
    "iu/l": "IU/L",
    "u/l": "U/L",
    "x10^3/ul": "x10^3/µL",
    "10^3/ul": "x10^3/µL",
    "/ul": "/µL",
}


def normalize_unit(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = re.sub(r"\s+", "", raw.strip())
    lowered = key.lower().replace("μ", "µ")
    if lowered in UNIT_MAP:
        return UNIT_MAP[lowered]
    for candidate, canonical in UNIT_MAP.items():
        if candidate.lower() == lowered:
            return canonical
    return key
