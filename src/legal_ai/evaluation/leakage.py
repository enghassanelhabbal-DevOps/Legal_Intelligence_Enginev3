"""leakage.py — Leakage-aware grouping, deterministic splits, and overlap checks.

Implements DATA_GOVERNANCE.md's leakage/contamination requirements and
Stage 1's exit criterion "held-out evaluation split is protected".

Two distinct concerns, kept separate on purpose:

1. `group_key_for` / `assign_groups`: decide which records must never be
   split across train/val/test because they share semantic identity
   (same law, same document, same case, etc).
2. `check_overlap`: given two already-materialized datasets (e.g. the
   952-article corpus and an eval-query set derived from it), detect
   whether the second leaks into the first at the exact/near-exact text
   or identifier level.

Both are deterministic and seeded; no randomness escapes the recorded seed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from src.legal_ai.core.exceptions import DatasetLeakageError, DatasetSplitError
from src.legal_ai.ingestion.case_citation_extraction import extract_case_citation

# Grouping key preference order for legal-document-shaped records.
# DATA_GOVERNANCE.md §leakage: prefer source/law/document/case-level grouping
# over random record-level splitting.
# "citation_key" is checked FIRST (DR-021): for judicial/case-ruling
# records, law_name/law_id is a shared topic label across many unrelated
# cases (e.g. "المنع من سماع الدعوى" appears on 5+ distinct rulings) and
# would incorrectly group unrelated cases into one leakage-safety cluster
# if used as the grouping key. The case citation (appeal number + year +
# technical office) is the correct, precise grouping identity for those
# records; it is absent (None) for legislative records, which correctly
# fall through to law_id.
_DEFAULT_GROUP_FIELDS = [
    "citation_key",
    "law_id",
    "document_id",
    "source_id",
    "case_id",
    "question_group",
]


def enrich_with_citation_key(record: dict[str, Any], text_field: str = "text") -> dict[str, Any]:
    """Return a copy of `record` with a `citation_key` field populated from
    its case citation, if it is a judicial/case-ruling record. Non-judicial
    records (or records where citation extraction fails) get
    citation_key=None, so they fall through to the next grouping field
    rather than being forced into a fabricated group."""
    text = record.get(text_field, "")
    citation = extract_case_citation(str(text)) if text else None
    enriched = dict(record)
    enriched["citation_key"] = citation.citation_key() if citation else None
    return enriched


def group_key_for(record: dict[str, Any], group_fields: list[str] | None = None) -> str:
    """Return the grouping identity for a record.

    Uses the first present, non-empty field from `group_fields` (default
    preference order above). Falls back to the record's own identifier if no
    grouping field is present — meaning it is its own group (no assumed
    relationship), which is the safe default, not a guess.
    """
    fields_to_try = group_fields or _DEFAULT_GROUP_FIELDS
    for f in fields_to_try:
        val = record.get(f)
        if val not in (None, ""):
            return f"{f}:{val}"
    fallback_id = record.get("document_id") or record.get("id") or repr(sorted(record.items()))
    return f"record:{fallback_id}"


def _stable_bucket(key: str, seed: int, num_buckets: int = 1000) -> int:
    """Deterministic seeded hash bucket in [0, num_buckets)."""
    h = hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
    return int(h, 16) % num_buckets


@dataclass
class SplitResult:
    strategy: str
    seed: int
    group_fields: list[str]
    assignments: dict[str, str] = field(default_factory=dict)  # record_id -> split name
    group_count: int = 0
    split_sizes: dict[str, int] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "seed": self.seed,
            "group_fields": self.group_fields,
            "group_count": self.group_count,
            "split_sizes": self.split_sizes,
            "rationale": self.rationale,
        }


def assign_groups(
    records: list[dict[str, Any]],
    *,
    id_field: str = "document_id",
    group_fields: list[str] | None = None,
    seed: int = 42,
    ratios: dict[str, float] | None = None,
) -> SplitResult:
    """Deterministically assign records to splits at group granularity.

    Records sharing a group key are always assigned to the same split, which
    is what prevents e.g. two chunks of the same law article ending up on
    both sides of a train/test boundary.

    Raises DatasetSplitError if ratios do not sum to ~1.0 or records is empty.
    """
    if not records:
        raise DatasetSplitError("Cannot split an empty dataset.")

    ratios = ratios or {"train": 0.7, "validation": 0.15, "held_out_test": 0.15}
    total_ratio = sum(ratios.values())
    if abs(total_ratio - 1.0) > 1e-6:
        raise DatasetSplitError(f"Split ratios must sum to 1.0, got {total_ratio}")

    fields_to_try = group_fields or _DEFAULT_GROUP_FIELDS
    groups: dict[str, list[str]] = {}
    for rec in records:
        gkey = group_key_for(rec, fields_to_try)
        rec_id = str(rec.get(id_field, gkey))
        groups.setdefault(gkey, []).append(rec_id)

    # Deterministic ordering independent of dict/set iteration order.
    ordered_group_keys = sorted(groups.keys())

    # Cumulative-ratio boundaries mapped onto the stable hash bucket space.
    boundaries: list[tuple[str, int]] = []
    cumulative = 0.0
    for split_name, ratio in ratios.items():
        cumulative += ratio
        boundaries.append((split_name, int(round(cumulative * 1000))))

    assignments: dict[str, str] = {}
    split_sizes: dict[str, int] = {name: 0 for name in ratios}
    for gkey in ordered_group_keys:
        bucket = _stable_bucket(gkey, seed)
        split_name = boundaries[-1][0]
        for name, upper in boundaries:
            if bucket < upper:
                split_name = name
                break
        for rec_id in groups[gkey]:
            assignments[rec_id] = split_name
            split_sizes[split_name] += 1

    rationale = (
        f"Grouped by first-present field of {fields_to_try} to avoid splitting "
        f"records that share law/document/case identity across train/val/test; "
        f"{len(ordered_group_keys)} groups assigned via seeded hash bucketing (seed={seed})."
    )

    return SplitResult(
        strategy="grouped_hash_split_v1",
        seed=seed,
        group_fields=fields_to_try,
        assignments=assignments,
        group_count=len(ordered_group_keys),
        split_sizes=split_sizes,
        rationale=rationale,
    )


@dataclass
class OverlapReport:
    exact_text_overlap: int = 0
    exact_id_overlap: int = 0
    overlap_examples: list[str] = field(default_factory=list)
    candidate_records_checked: int = 0
    candidate_records_with_text_field: int = 0
    candidate_records_with_id_field: int = 0
    is_clean: bool = True
    is_meaningful: bool = True
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exact_text_overlap": self.exact_text_overlap,
            "exact_id_overlap": self.exact_id_overlap,
            "overlap_examples": self.overlap_examples,
            "candidate_records_checked": self.candidate_records_checked,
            "candidate_records_with_text_field": self.candidate_records_with_text_field,
            "candidate_records_with_id_field": self.candidate_records_with_id_field,
            "is_clean": self.is_clean,
            "is_meaningful": self.is_meaningful,
            "warnings": self.warnings,
        }


def check_overlap(
    protected: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    *,
    text_field: str = "raw_text",
    id_field: str = "document_id",
    candidate_text_field: str | None = None,
    candidate_id_field: str | None = None,
    max_examples: int = 10,
) -> OverlapReport:
    """Check whether `candidate` (e.g. a new training/tuning set) overlaps a
    `protected` dataset (e.g. a held-out benchmark) at text or id level.

    This is an exact-match check by design (bounded, deterministic, no model
    calls) — it will catch verbatim leakage but not paraphrase-level leakage,
    which is a documented limitation, not a silent gap.

    `candidate_text_field`/`candidate_id_field` let the candidate use different
    field names than the protected set (e.g. eval-query sets use `query` and
    `relevant_document_ids` rather than `raw_text`/`document_id`). If neither
    is supplied and the candidate schema does not contain `text_field`/
    `id_field` at all, the result is marked `is_meaningful=False` with an
    explicit warning instead of silently reporting a "clean" pass — a check
    that can't check anything must not look identical to a check that passed.
    """
    protected_texts = {str(r.get(text_field, "")).strip() for r in protected if r.get(text_field)}
    protected_ids = {str(r.get(id_field)) for r in protected if r.get(id_field) is not None}

    c_text_field = candidate_text_field or text_field
    c_id_field = candidate_id_field or id_field

    report = OverlapReport(candidate_records_checked=len(candidate))
    for rec in candidate:
        text = str(rec.get(c_text_field, "")).strip()
        rec_id = rec.get(c_id_field)
        if text:
            report.candidate_records_with_text_field += 1
        if rec_id is not None:
            report.candidate_records_with_id_field += 1
        if text and text in protected_texts:
            report.exact_text_overlap += 1
            if len(report.overlap_examples) < max_examples:
                report.overlap_examples.append(f"text_match:{rec_id}")
        if rec_id is not None and str(rec_id) in protected_ids:
            report.exact_id_overlap += 1

    report.is_clean = report.exact_text_overlap == 0 and report.exact_id_overlap == 0

    checked_something = (
        report.candidate_records_with_text_field > 0
        or report.candidate_records_with_id_field > 0
    )
    if candidate and not checked_something:
        report.is_meaningful = False
        report.warnings.append(
            f"Candidate records have neither '{c_text_field}' nor '{c_id_field}' "
            f"populated — this check compared nothing and its 'is_clean=True' "
            f"result must NOT be treated as evidence of no leakage. Pass "
            f"candidate_text_field/candidate_id_field matching the candidate's "
            f"actual schema."
        )

    return report


def enforce_no_overlap(
    protected: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    *,
    text_field: str = "raw_text",
    id_field: str = "document_id",
    candidate_text_field: str | None = None,
    candidate_id_field: str | None = None,
    require_meaningful: bool = True,
) -> OverlapReport:
    """Same as check_overlap but raises DatasetLeakageError if contaminated,
    and (by default) also raises if the check could not check anything —
    a vacuous "clean" result must not silently pass a CI gate.
    """
    report = check_overlap(
        protected,
        candidate,
        text_field=text_field,
        id_field=id_field,
        candidate_text_field=candidate_text_field,
        candidate_id_field=candidate_id_field,
    )
    if require_meaningful and not report.is_meaningful:
        raise DatasetLeakageError(
            f"Leakage check was vacuous, not clean: {report.warnings}"
        )
    if not report.is_clean:
        raise DatasetLeakageError(
            f"Leakage detected: {report.exact_text_overlap} exact text overlaps, "
            f"{report.exact_id_overlap} exact id overlaps between protected and "
            f"candidate datasets. Examples: {report.overlap_examples}"
        )
    return report


__all__ = [
    "SplitResult",
    "OverlapReport",
    "group_key_for",
    "enrich_with_citation_key",
    "assign_groups",
    "check_overlap",
    "enforce_no_overlap",
]
