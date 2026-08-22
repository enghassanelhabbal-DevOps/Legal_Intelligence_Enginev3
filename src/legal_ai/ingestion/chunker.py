"""chunker.py — Article-aware document chunking for Arabic legislative texts.

Migrated from legal_ai/ingestion.py.
"""

from __future__ import annotations

import re
from typing import Any

# Pattern matches "مادة 5", "المادة رقم 12", etc.
_ARTICLE_RE = re.compile(r"(مادة|المادة)\s*(?:رقم\s*)?(\d+)", flags=re.IGNORECASE)

# Default maximum chunk size in characters
DEFAULT_MAX_CHARS = 2_000


def article_aware_chunk(
    text: str, max_chars: int = DEFAULT_MAX_CHARS
) -> list[dict[str, Any]]:
    """Split a legislative text into article-aware chunks.

    Returns:
        List of dicts:
            {
                "article_id": str | None,
                "text": str,
                "chunk_index": int,
                "chunk_count": int,
            }

    Behavior:
    - Split by explicit article headings (مادة / المادة).
    - Fall back to windowed splitting when no headings are found.
    - Articles larger than *max_chars* are split into multiple chunks,
      each preserving the parent article_id.
    """
    matches = list(_ARTICLE_RE.finditer(text))

    if not matches:
        # Fallback: simple windowed split
        total = (len(text) + max_chars - 1) // max_chars
        return [
            {
                "article_id": None,
                "text": text[i : i + max_chars].strip(),
                "chunk_index": idx,
                "chunk_count": total,
            }
            for idx, i in enumerate(range(0, len(text), max_chars))
        ]

    # Build article spans
    spans: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        article_num = m.group(2)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((article_num, text[start:end].strip()))

    # Chunk each article individually
    out: list[dict[str, Any]] = []
    for article_id, body in spans:
        if len(body) <= max_chars:
            out.append(
                {"article_id": article_id, "text": body, "chunk_index": 0, "chunk_count": 1}
            )
            continue
        parts = [body[i : i + max_chars].strip() for i in range(0, len(body), max_chars)]
        for idx, part in enumerate(parts):
            out.append(
                {
                    "article_id": article_id,
                    "text": part,
                    "chunk_index": idx,
                    "chunk_count": len(parts),
                }
            )
    return out


def chunk_document(
    doc: dict[str, Any], max_chars: int = DEFAULT_MAX_CHARS
) -> list[dict[str, Any]]:
    """Create chunks for a document dict with keys 'document_id', 'raw_text', 'metadata'.

    Returns a list of chunk dicts with full provenance fields.
    """
    content: str = doc.get("raw_text", "") or ""
    chunks = article_aware_chunk(content, max_chars=max_chars)
    return [
        {
            "document_id": doc.get("document_id"),
            "article_id": c.get("article_id"),
            "chunk_index": c.get("chunk_index"),
            "chunk_count": c.get("chunk_count"),
            "metadata": doc.get("metadata", {}),
            "text": c.get("text"),
        }
        for c in chunks
    ]


__all__ = ["article_aware_chunk", "chunk_document", "DEFAULT_MAX_CHARS"]
