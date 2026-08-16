from __future__ import annotations

import re


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 10:
        return digits[-10:]
    if len(digits) >= 7:
        return digits
    return None
