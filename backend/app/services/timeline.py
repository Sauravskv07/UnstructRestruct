from __future__ import annotations

from collections import defaultdict


def cluster_timeline(items: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[item.get("date") or "undated"].append(item)

    dated = sorted((key for key in groups if key != "undated"), reverse=True)
    order = dated + (["undated"] if "undated" in groups else [])
    clusters = []
    for date in order:
        documents = groups[date]
        descriptions = [_document_description(doc) for doc in documents]
        types = sorted({(doc.get("document_type") or "document").replace("_", " ") for doc in documents})
        clusters.append(
            {
                "date": None if date == "undated" else date,
                "title": "Undated" if date == "undated" else date,
                "type_label": ", ".join(types),
                "description": "; ".join(descriptions),
                "document_count": len(documents),
                "documents": documents,
            }
        )
    return clusters


def _document_description(doc: dict) -> str:
    kind = (doc.get("document_type") or "document").replace("_", " ")
    summary = [part for part in (doc.get("summary") or []) if part]
    if not summary:
        return f"{kind}: {doc.get('filename') or 'record'}"
    return f"{kind}: {', '.join(summary[:4])}"
