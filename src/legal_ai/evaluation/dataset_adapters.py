"""dataset_adapters.py — Schema adapters mapping a source dataset's native
record shape into the canonical LegalDocument-compatible shape the profiler
and leakage tools expect.

This is what makes "a second dataset arriving later" require zero bespoke
pipeline code (Stage 1 exit criterion): each adapter is a pure function
`raw_record -> canonical_dict`, registered by name, selected via
`--adapter <name>` on the CLI. Adding a third dataset means adding one
function here, not a new pipeline.

Identifier honesty rule: when a source dataset has no native stable record
id, the adapter must derive one deterministically from content (documented
as such) rather than inventing a sequence number that looks like an
original identifier. See `_content_derived_id`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.legal_ai.ingestion.validation import hash_document

CANONICAL_FIELDS = [
    "document_id",
    "jurisdiction",
    "law_id",
    "law_name",
    "article_id",
    "raw_text",
    "normalized_text",
    "embedding_text",
    "version_id",
    "source",
]


def _content_derived_id(text: str, salt: str = "") -> str:
    """Deterministic id derived from content, explicitly NOT a claimed
    original identifier. Reuses the canonical hashing primitive."""
    return "content:" + hash_document({"raw_text": f"{salt}|{text}"})[:16]


def identity_adapter(record: dict[str, Any]) -> dict[str, Any]:
    """Pass-through adapter for records already in canonical shape
    (e.g. legal_documents.json / the existing 952-article corpus)."""
    return record


def dataflare_egypt_legal_corpus_adapter(record: dict[str, Any]) -> dict[str, Any]:
    """Maps dataflare/egypt-legal-corpus's public schema
    (`law_name`, `categories`, `text`, `tokens`) into canonical shape.

    Documented, non-guessed assumptions (see
    docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md):
      - jurisdiction "EG": asserted by the dataset's own name/card, marked
        `jurisdiction_source: "dataset_name_declared"` rather than presented
        as independently verified.
      - article_id: NOT available at record level for this schema — records
        can span whole laws (see ingestion/article_segmentation.py for the
        structure-extraction step required before article-level identity
        exists). Left as the canonical `unknown` sentinel, never guessed.
      - document_id: no native id in the public schema; derived
        deterministically from (law_name, text) content hash and prefixed
        `content:` so it is never mistaken for a source-provided identifier.
    """
    law_name = record.get("law_name", "") or ""
    text = record.get("text", "") or ""
    categories = record.get("categories")

    return {
        "document_id": _content_derived_id(text, salt=law_name),
        "jurisdiction": "EG",
        "jurisdiction_source": "dataset_name_declared",  # extra, non-canonical diagnostic field
        "law_id": law_name,
        "law_name": law_name,
        "article_id": None,  # unknown at record level; requires segmentation
        "raw_text": text,
        "normalized_text": text,  # normalization pipeline runs at ingestion, not here
        "embedding_text": text,
        "version_id": None,
        "source": "dataflare/egypt-legal-corpus",
        "categories": categories,  # passthrough, not part of CANONICAL_FIELDS
        "token_count_declared": record.get("tokens"),
    }


ADAPTERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "identity": identity_adapter,
    "dataflare_egypt_legal_corpus": dataflare_egypt_legal_corpus_adapter,
}


def apply_adapter(records: list[dict[str, Any]], adapter_name: str) -> list[dict[str, Any]]:
    if adapter_name not in ADAPTERS:
        raise ValueError(
            f"Unknown adapter {adapter_name!r}. Available: {sorted(ADAPTERS)}"
        )
    adapter = ADAPTERS[adapter_name]
    return [adapter(r) for r in records]


__all__ = [
    "CANONICAL_FIELDS",
    "ADAPTERS",
    "identity_adapter",
    "dataflare_egypt_legal_corpus_adapter",
    "apply_adapter",
]
