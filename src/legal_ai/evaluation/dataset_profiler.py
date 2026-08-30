"""dataset_profiler.py — Deterministic, bounded dataset profiling (Stage 1).

Produces a machine-readable quality profile (DATA_GOVERNANCE.md §16) for any
list-of-dict dataset shaped like the canonical `LegalDocument` fields, or a
generic record shape when profiling a non-corpus dataset (e.g. an eval-query
set built by scripts/build_eval_set.py).

Deliberately stdlib-only (no pandas): corpora at this stage (hundreds to low
thousands of records) do not justify the dependency, per
RESOURCE_RELIABILITY_SPEC.md's "no unnecessary dependencies" and Stage 1's
"as lightweight as possible" instruction. All operations are O(n) single-pass
or O(n log n) sort, with no per-record model loading.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from src.legal_ai.ingestion.validation import hash_document

# Canonical LegalDocument required fields (core/contracts.py).
_LEGAL_DOCUMENT_FIELDS = [
    "document_id",
    "jurisdiction",
    "law_id",
    "law_name",
    "article_id",
    "raw_text",
    "normalized_text",
    "embedding_text",
]

# Cheap heuristic Arabic-script detector (U+0600–U+06FF core Arabic block).
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _detect_language(text: str) -> str:
    """Bounded, dependency-free language heuristic: arabic / latin / mixed / empty."""
    if not text or not text.strip():
        return "empty"
    has_ar = bool(_ARABIC_RE.search(text))
    has_lat = bool(_LATIN_RE.search(text))
    if has_ar and has_lat:
        return "arabic_english_mixed"
    if has_ar:
        return "arabic"
    if has_lat:
        return "latin"
    return "other"


def _text_len_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n < 50:
        return "1-49"
    if n < 200:
        return "50-199"
    if n < 500:
        return "200-499"
    if n < 1500:
        return "500-1499"
    return "1500+"


@dataclass
class QualityProfile:
    record_count: int = 0
    empty_records: int = 0
    missing_required_fields: dict[str, int] = field(default_factory=dict)
    malformed_records: int = 0
    invalid_identifiers: int = 0

    duplicate_count: int = 0
    near_duplicate_count: int = 0

    text_length_distribution: dict[str, int] = field(default_factory=dict)
    language_distribution: dict[str, int] = field(default_factory=dict)
    jurisdiction_distribution: dict[str, int] = field(default_factory=dict)
    law_distribution: dict[str, int] = field(default_factory=dict)
    date_distribution: dict[str, int] = field(default_factory=dict)

    citation_completeness: float = 0.0  # fraction of records with a non-empty article_id
    content_hash: str = "unknown"

    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_count": self.record_count,
            "empty_records": self.empty_records,
            "missing_required_fields": self.missing_required_fields,
            "malformed_records": self.malformed_records,
            "invalid_identifiers": self.invalid_identifiers,
            "duplicate_count": self.duplicate_count,
            "near_duplicate_count": self.near_duplicate_count,
            "text_length_distribution": self.text_length_distribution,
            "language_distribution": self.language_distribution,
            "jurisdiction_distribution": self.jurisdiction_distribution,
            "law_distribution": self.law_distribution,
            "date_distribution": self.date_distribution,
            "citation_completeness": self.citation_completeness,
            "content_hash": self.content_hash,
            "warnings": self.warnings,
        }


def profile_dataset(
    records: list[dict[str, Any]],
    *,
    text_field: str = "raw_text",
    id_field: str = "document_id",
    required_fields: list[str] | None = None,
) -> QualityProfile:
    """Profile a list of record dicts. Bounded, single-pass, deterministic.

    Args:
        records: list of dataset records (dicts).
        text_field: field used for length/language/near-dup analysis.
        id_field: field used for identifier validity checks.
        required_fields: fields that must be present and non-empty; defaults
            to the canonical LegalDocument schema when records look like
            LegalDocuments (i.e. contain 'raw_text'), otherwise just [id_field].
    """
    profile = QualityProfile(record_count=len(records))

    if required_fields is None:
        required_fields = (
            _LEGAL_DOCUMENT_FIELDS if records and text_field in records[0] else [id_field]
        )

    missing_counts: Counter[str] = Counter()
    length_buckets: Counter[str] = Counter()
    lang_counts: Counter[str] = Counter()
    jurisdiction_counts: Counter[str] = Counter()
    law_counts: Counter[str] = Counter()

    seen_exact_text: Counter[str] = Counter()
    seen_normalized_text: Counter[str] = Counter()
    seen_ids: set[str] = set()
    id_collisions = 0
    citation_present = 0

    for rec in records:
        if not isinstance(rec, dict):
            profile.malformed_records += 1
            continue

        for f in required_fields:
            val = rec.get(f)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing_counts[f] += 1

        text = rec.get(text_field, "") or ""
        if not str(text).strip():
            profile.empty_records += 1

        length_buckets[_text_len_bucket(len(str(text)))] += 1
        lang_counts[_detect_language(str(text))] += 1

        jurisdiction = rec.get("jurisdiction")
        if jurisdiction:
            jurisdiction_counts[str(jurisdiction)] += 1

        law = rec.get("law_id") or rec.get("law_name")
        if law:
            law_counts[str(law)] += 1

        article_id = rec.get("article_id")
        if article_id not in (None, ""):
            citation_present += 1

        rec_id = rec.get(id_field)
        if rec_id is None or str(rec_id).strip() == "":
            profile.invalid_identifiers += 1
        else:
            rec_id = str(rec_id)
            if rec_id in seen_ids:
                id_collisions += 1
            seen_ids.add(rec_id)

        if text:
            seen_exact_text[str(text)] += 1
            normalized = rec.get("normalized_text") or str(text)
            seen_normalized_text[str(normalized)] += 1

    profile.missing_required_fields = dict(missing_counts)
    profile.text_length_distribution = dict(length_buckets)
    profile.language_distribution = dict(lang_counts)
    profile.jurisdiction_distribution = dict(jurisdiction_counts)
    profile.law_distribution = dict(law_counts)
    profile.date_distribution = {"unknown": len(records)}  # no date fields in current schema

    profile.duplicate_count = sum(c - 1 for c in seen_exact_text.values() if c > 1)
    # Near-duplicate proxy: normalized-text collisions that are NOT already
    # counted as exact-text duplicates. Cheap, bounded, exact-string based —
    # not a semantic near-duplicate detector (documented limitation).
    exact_dupe_norms = {t for t, c in seen_exact_text.items() if c > 1}
    near_dupe_extra = 0
    for norm_text, count in seen_normalized_text.items():
        if count > 1 and norm_text not in exact_dupe_norms:
            near_dupe_extra += count - 1
    profile.near_duplicate_count = near_dupe_extra

    profile.citation_completeness = (
        citation_present / len(records) if records else 0.0
    )
    profile.invalid_identifiers += id_collisions

    if id_collisions:
        profile.warnings.append(
            f"{id_collisions} duplicate {id_field} values detected (non-unique identifiers)."
        )
    if profile.empty_records:
        profile.warnings.append(f"{profile.empty_records} records have empty '{text_field}'.")

    # Reuse the existing content-hash primitive (ingestion/validation.py) so
    # dataset-level content hashing stays a single canonical implementation.
    concatenated = "|".join(hash_document(r) for r in records if isinstance(r, dict))
    profile.content_hash = hash_document({"raw_text": concatenated})

    return profile


__all__ = ["QualityProfile", "profile_dataset"]
