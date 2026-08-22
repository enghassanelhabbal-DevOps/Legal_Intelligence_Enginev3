"""metrics.py — Retrieval evaluation metrics.

Implements MRR and Recall@k as used in the protected baseline.
Any retrieval or reranker change must report before/after these metrics
(ARCHITECTURE_CONTRACT.md §Protected retrieval baseline).
"""

from __future__ import annotations

from collections.abc import Sequence


def compute_mrr(
    retrieved_ids: Sequence[str],
    relevant_ids: Sequence[str],
) -> float:
    """Mean Reciprocal Rank (MRR) for a single query.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids:  Set of ground-truth relevant document IDs.

    Returns:
        Reciprocal rank (1/rank) of the first relevant hit, or 0.0 if none found.
    """
    rel = set(relevant_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in rel:
            return 1.0 / rank
    return 0.0


def compute_recall_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: Sequence[str],
    k: int,
) -> float:
    """Recall@k for a single query.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids:  Ground-truth relevant document IDs.
        k:             Cut-off depth.

    Returns:
        Fraction of relevant docs found in the top-k results.
        Returns 0.0 if relevant_ids is empty.
    """
    if not relevant_ids:
        return 0.0
    rel = set(relevant_ids)
    top_k = set(list(retrieved_ids)[:k])
    return len(rel & top_k) / len(rel)


def mean_mrr(results: list[dict]) -> float:
    """Compute MRR averaged over a list of query result dicts.

    Each dict should have keys:
      - 'retrieved': list of retrieved doc IDs (ordered)
      - 'relevant':  list of ground-truth relevant doc IDs
    """
    if not results:
        return 0.0
    return sum(
        compute_mrr(r["retrieved"], r["relevant"]) for r in results
    ) / len(results)


def mean_recall_at_k(results: list[dict], k: int) -> float:
    """Compute Recall@k averaged over a list of query result dicts."""
    if not results:
        return 0.0
    return sum(
        compute_recall_at_k(r["retrieved"], r["relevant"], k) for r in results
    ) / len(results)


__all__ = ["compute_mrr", "compute_recall_at_k", "mean_mrr", "mean_recall_at_k"]
