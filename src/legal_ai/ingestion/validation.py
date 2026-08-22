"""validation.py — Document validation and hashing utilities.

Provides:
  - hash_document: deterministic SHA-256 hash for deduplication and change detection
  - validate_document: structural validation raising IngestionError on bad input
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.legal_ai.core.exceptions import IngestionError

# Required top-level keys for a canonical legal document dict
_REQUIRED_KEYS: list[str] = [
    "document_id",
    "jurisdiction",
    "law_id",
    "law_name",
    "article_id",
    "raw_text",
    "normalized_text",
    "embedding_text"
]


def hash_document(doc: dict[str, Any]) -> str:
    """Return a SHA-256 hex digest of the document's canonical content.

    The hash is computed over the JSON-serialised *raw_text* field only so that
    metadata updates (e.g., source URL) do not invalidate the embedding cache.
    """
    content = doc.get("raw_text", "") or ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_document(doc: Any) -> None:
    """Raise IngestionError if *doc* does not satisfy the minimum schema.

    Rules:
      - Must be a dict
      - Must contain all required keys for LegalDocument
      - 'raw_text' must be a non-empty string
    """
    if not isinstance(doc, dict):
        raise IngestionError(f"Document must be a dict, got {type(doc).__name__}")
    for key in _REQUIRED_KEYS:
        if key not in doc:
            raise IngestionError(f"Document missing required key: '{key}'")
    content = doc.get("raw_text")
    if not isinstance(content, str) or not content.strip():
        raise IngestionError(
            f"Document 'raw_text' must be a non-empty string (doc id={doc.get('document_id')!r})"
        )


def validate_documents(docs: list[Any]) -> None:
    """Validate a list of documents, raising IngestionError on the first failure."""
    if not isinstance(docs, list):
        raise IngestionError("'documents' must be a list")
    for i, doc in enumerate(docs):
        try:
            validate_document(doc)
        except IngestionError as exc:
            raise IngestionError(f"Validation failed at index {i}: {exc}") from exc


__all__ = ["hash_document", "validate_document", "validate_documents"]
