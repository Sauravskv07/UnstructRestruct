from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as date_parser


def normalize_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        # Ambiguous numeric dates are treated as day-first (DD/MM/YYYY),
        # matching the assignment examples and typical Indian lab reports.
        parsed = date_parser.parse(text, dayfirst=True, yearfirst=False, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None
    if parsed.year < 1900 or parsed.year > datetime.now(timezone.utc).year + 2:
        return None
    return parsed.date().isoformat()
