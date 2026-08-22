"""builder.py — Evidence selection and grounded context construction.

Extracted from legal_rag_engine.py (build_grounded_context).
Responsibility: turn ranked retrieval hits into a compact, cited LLM context.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def build_grounded_context(
    results: Sequence[dict[str, Any]],
    max_chars: int = 14_000,
) -> str:
    """Build the grounded context string passed to the LLM.

    Iterates results in order, appending SOURCE blocks until *max_chars* is
    reached.  Each block references its source so the LLM can produce citations.

    Args:
        results: Ordered retrieval result dicts (as returned by HybridRetriever.retrieve).
        max_chars: Hard character budget for the context window.

    Returns:
        A formatted string with numbered [SOURCE N] blocks.
    """
    blocks: list[str] = []
    current = 0
    for i, item in enumerate(results, start=1):
        title = " ".join(str(item.get("law_name", "")).split()) or "مصدر قانوني"
        content = " ".join(str(item.get("text", "")).split())
        article_id = item.get("article_id", "")
        block = (
            f"[SOURCE {i}]\n"
            f"العنوان: {title} - المادة {article_id}\n"
            f"النص: {content}\n"
            f"معرّف المصدر: {item.get('document_id')}"
        )
        if current + len(block) > max_chars:
            break
        blocks.append(block)
        current += len(block)
    return "\n\n".join(blocks)


def select_evidence(
    results: Sequence[dict[str, Any]],
    max_chars: int = 14_000,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Select and filter evidence items from retrieval results.

    Filters out items below *min_score* and respects *max_chars* budget.
    Returns a list of result dicts that will be used in context building.
    """
    selected: list[dict[str, Any]] = []
    current = 0
    for item in results:
        score = item.get("reranker_score") or item.get("dense_score") or 0.0
        if float(score) < min_score:
            continue
        content = str(item.get("text", ""))
        if current + len(content) > max_chars:
            break
        selected.append(item)
        current += len(content)
    return selected


__all__ = ["build_grounded_context", "select_evidence"]
