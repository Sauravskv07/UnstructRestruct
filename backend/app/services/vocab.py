from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from app.db.models import DiagnosticReport, LabResult, Medication, VocabularyAlias, VocabularyTerm
from app.services.normalization.names import (
    MED_ALIASES,
    MED_LABELS,
    STUDY_ALIASES,
    STUDY_LABELS,
    TEST_ALIASES,
    TEST_LABELS,
    _key,
    human_label,
    normalize_medication_name,
    normalize_study_name,
    normalize_test_name,
)

LAB = "lab_test"
MED = "medication"
DX = "diagnostic"
KINDS = {LAB, MED, DX}
SEARCH_CUTOFF = 58
SEARCH_LIMIT = 12


@dataclass
class VocabHit:
    id: str
    label: str
    in_chart: bool
    score: int


def seed_vocabulary(db: Session) -> None:
    _seed_kind(db, LAB, TEST_ALIASES, TEST_LABELS)
    _seed_kind(db, MED, MED_ALIASES, MED_LABELS)
    _seed_kind(db, DX, STUDY_ALIASES, STUDY_LABELS)
    db.flush()
    consolidate_vocabulary(db)
    db.flush()


def backfill_vocabulary(db: Session) -> None:
    for row in db.query(DiagnosticReport).all():
        if not row.canonical_study and row.study:
            row.canonical_study = normalize_study_name(row.study)
    for canonical, raw in db.query(LabResult.canonical_name, LabResult.raw_name).all():
        observe(db, LAB, canonical, raw)
    for canonical, raw in db.query(Medication.canonical_name, Medication.raw_name).all():
        observe(db, MED, canonical, raw)
    for canonical, raw in db.query(DiagnosticReport.canonical_study, DiagnosticReport.study).all():
        observe(db, DX, canonical, raw)
    db.flush()
    consolidate_vocabulary(db)
    db.flush()


def _normalize_kind(kind: str, value: str | None) -> str | None:
    if kind == LAB:
        return normalize_test_name(value)
    if kind == MED:
        return normalize_medication_name(value)
    if kind == DX:
        return normalize_study_name(value)
    return None


def observe(db: Session, kind: str, canonical: str | None, raw: str | None = None, label: str | None = None) -> None:
    if kind not in KINDS:
        return
    canon = _normalize_kind(kind, canonical) or _normalize_kind(kind, raw) or _key(raw or "") or None
    if not canon:
        return
    labels = {LAB: TEST_LABELS, MED: MED_LABELS, DX: STUDY_LABELS}[kind]
    display = label or human_label(canon, labels)
    existing = (
        db.query(VocabularyTerm)
        .filter(VocabularyTerm.kind == kind, VocabularyTerm.canonical == canon)
        .one_or_none()
    )
    if existing is None and not _pending_term(db, kind, canon):
        db.add(VocabularyTerm(kind=kind, canonical=canon, label=display))
    elif existing is not None and canon in labels and existing.label != labels[canon]:
        existing.label = labels[canon]
    _alias(db, kind, canon, canon)
    _alias(db, kind, canon, _key(display))
    _alias(db, kind, canon, _key(canonical or ""))
    if raw:
        _alias(db, kind, canon, _key(raw))
        compact = _key(raw).replace(" ", "")
        if compact:
            _alias(db, kind, canon, compact)


def consolidate_vocabulary(db: Session) -> None:
    for kind in KINDS:
        terms = db.query(VocabularyTerm).filter(VocabularyTerm.kind == kind).all()
        for term in terms:
            wanted = _normalize_kind(kind, term.canonical)
            if not wanted or wanted == term.canonical:
                continue
            observe(db, kind, wanted, term.canonical)
            db.flush()
            db.query(VocabularyAlias).filter(
                VocabularyAlias.kind == kind,
                VocabularyAlias.canonical == term.canonical,
            ).update({"canonical": wanted})
            db.delete(term)


def chart_term_ids(db: Session, kind: str, tokens: set[str]) -> set[str]:
    """Map raw/canonical strings seen on a chart onto vocabulary ids."""
    expanded: set[str] = set()
    for token in tokens:
        if not token or not str(token).strip():
            continue
        raw = str(token).strip().lower()
        expanded.add(raw)
        expanded.add(_key(raw))
        expanded.add(_key(raw).replace(" ", ""))
        expanded.add(raw.replace(" ", "_"))
        normalized = _normalize_kind(kind, token)
        if normalized:
            expanded.add(normalized)
    if not expanded:
        return set()
    aliases = db.query(VocabularyAlias).filter(VocabularyAlias.kind == kind).all()
    by_alias = {row.alias_key: row.canonical for row in aliases}
    ids: set[str] = set(expanded)
    for token in list(expanded):
        if token in by_alias:
            ids.add(by_alias[token])
    return ids


def search(
    db: Session,
    kind: str,
    query: str,
    in_chart: set[str],
    limit: int = SEARCH_LIMIT,
) -> list[VocabHit]:
    if kind not in KINDS:
        return []
    terms = {row.canonical: row.label for row in db.query(VocabularyTerm).filter(VocabularyTerm.kind == kind)}
    aliases: dict[str, list[str]] = {canonical: [] for canonical in terms}
    for row in db.query(VocabularyAlias).filter(VocabularyAlias.kind == kind):
        aliases.setdefault(row.canonical, []).append(row.alias_key)
        terms.setdefault(row.canonical, human_label(row.canonical, {}))

    q = (query or "").strip()
    if not q:
        hits = [
            VocabHit(id=canonical, label=terms[canonical], in_chart=True, score=100)
            for canonical in terms
            if canonical in in_chart
        ]
        hits.sort(key=lambda item: item.label.lower())
        return hits[:limit]

    choices: dict[str, str] = {}
    for canonical, label in terms.items():
        parts = [canonical, label, canonical.replace("_", " "), *aliases.get(canonical, [])]
        choices[canonical] = " ".join(dict.fromkeys(part for part in parts if part))

    ranked = process.extract(
        q,
        choices,
        scorer=fuzz.WRatio,
        limit=max(limit * 3, 20),
        score_cutoff=SEARCH_CUTOFF,
    )
    seen: set[str] = set()
    hits: list[VocabHit] = []
    for _text, score, canonical in ranked:
        resolved = _normalize_kind(kind, canonical) or canonical
        if resolved in seen:
            continue
        seen.add(resolved)
        chart = _hit_on_chart(resolved, in_chart, aliases.get(resolved, []) + aliases.get(canonical, []))
        hits.append(
            VocabHit(
                id=resolved,
                label=terms.get(resolved, terms.get(canonical, human_label(resolved, {}))),
                in_chart=chart,
                score=int(score) + (12 if chart else 0),
            )
        )
    hits.sort(key=lambda item: (not item.in_chart, -item.score, item.label.lower()))
    return hits[:limit]


def _hit_on_chart(canonical: str, in_chart: set[str], alias_keys: list[str]) -> bool:
    if canonical in in_chart:
        return True
    return any(key in in_chart for key in alias_keys)


def _seed_kind(db: Session, kind: str, aliases: dict[str, str], labels: dict[str, str]) -> None:
    for alias, canonical in aliases.items():
        observe(db, kind, canonical, alias, labels.get(canonical))


def _pending_term(db: Session, kind: str, canonical: str) -> bool:
    return any(
        isinstance(obj, VocabularyTerm) and obj.kind == kind and obj.canonical == canonical
        for obj in db.new
    )


def _pending_alias(db: Session, kind: str, key: str) -> bool:
    return any(
        isinstance(obj, VocabularyAlias) and obj.kind == kind and obj.alias_key == key
        for obj in db.new
    )


def _alias(db: Session, kind: str, canonical: str, alias_key: str | None) -> None:
    key = (alias_key or "").strip().lower()
    if not key:
        return
    exists = (
        db.query(VocabularyAlias)
        .filter(VocabularyAlias.kind == kind, VocabularyAlias.alias_key == key)
        .one_or_none()
    )
    if exists is not None or _pending_alias(db, kind, key):
        return
    db.add(VocabularyAlias(kind=kind, alias_key=key, canonical=canonical))
