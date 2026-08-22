"""hybrid.py — HybridRetriever: dense + BM25 fusion + reranking orchestration.

Extracted from legal_rag_engine.py.
Dependency flow (ARCHITECTURE_CONTRACT.md):
  retrieval → reranking   (reranker injected, not imported directly)
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

import numpy as np

from src.legal_ai.core.logging import get_logger
from src.legal_ai.core.models import PipelineConfig, RetrievalHit
from src.legal_ai.retrieval.bm25 import BM25
from src.legal_ai.retrieval.dense import DenseEncoder, DenseIndex

LOGGER = get_logger(__name__)


def _metadata_text(doc: dict) -> str:
    """Build the text representation used for dense retrieval and reranker input."""
    return str(doc.get("embedding_text", ""))


def _lexical_text(doc: dict) -> str:
    """Build the text used for BM25 indexing (law name gets a small boost)."""
    law_name = str(doc.get("law_name", "")).strip()
    norm = str(doc.get("normalized_text", "")).strip()
    return f"{law_name} {law_name} {norm}".strip()


class HybridRetriever:
    """Full hybrid pipeline: dense search → BM25 → candidate fusion → reranking.

    The reranker is optional and injected from outside so this module does not
    import from the reranking sub-package (respects the dependency flow).
    """

    def __init__(
        self,
        documents: list[dict[str, Any]],
        encoder: DenseEncoder,
        dense_index: DenseIndex,
        bm25: BM25,
        reranker: Any | None,   # src.legal_ai.reranking.Reranker — injected
        config: PipelineConfig,
    ) -> None:
        self.documents = documents
        self.encoder = encoder
        self.dense_index = dense_index
        self.bm25 = bm25
        self.reranker = reranker
        self.config = config

    # ------------------------------------------------------------------
    # Individual search heads
    # ------------------------------------------------------------------

    def dense_search(self, query: str, k: int | None = None) -> list[RetrievalHit]:
        k = k or self.config.dense_candidates
        q = self.encoder.encode_query(query)
        scores, indices = self.dense_index.search(q, k)
        results: list[RetrievalHit] = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
            if idx < 0:
                continue
            d = self.documents[int(idx)]
            results.append(
                RetrievalHit(
                    document_id=str(d["document_id"]),
                    index=int(idx),
                    text=d["raw_text"],
                    law_name=d.get("law_name", ""),
                    article_id=d.get("article_id", ""),
                    dense_score=float(score),
                )
            )
        return results

    def bm25_search(self, query: str, k: int | None = None) -> list[RetrievalHit]:
        k = k or self.config.bm25_candidates
        results: list[RetrievalHit] = []
        for _rank, (idx, score) in enumerate(self.bm25.top_n(query, k), start=1):
            d = self.documents[idx]
            results.append(
                RetrievalHit(
                    document_id=str(d["document_id"]),
                    index=idx,
                    text=d["raw_text"],
                    law_name=d.get("law_name", ""),
                    article_id=d.get("article_id", ""),
                    bm25_score=score,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Candidate fusion (dense-preserving)
    # ------------------------------------------------------------------

    @staticmethod
    def dense_preserving_union(
        dense: list[RetrievalHit],
        bm25: list[RetrievalHit],
        max_candidates: int,
    ) -> list[RetrievalHit]:
        """Merge dense + BM25 results keeping dense ordering at the head."""
        merged: dict[str, RetrievalHit] = {}
        for hit in dense:
            merged[hit.document_id] = RetrievalHit(**{**asdict(hit)})
        for hit in bm25:
            if hit.document_id in merged:
                merged[hit.document_id].bm25_score = hit.bm25_score
            else:
                merged[hit.document_id] = RetrievalHit(**{**asdict(hit)})

        ordered = [merged[x.document_id] for x in dense]
        dense_ids = {d.document_id for d in dense}
        ordered += [merged[x.document_id] for x in bm25 if x.document_id not in dense_ids]
        return ordered[:max_candidates]

    # ------------------------------------------------------------------
    # Score fusion (dense-prior + reranker)
    # ------------------------------------------------------------------

    @staticmethod
    def _minmax(values: np.ndarray) -> np.ndarray:
        if len(values) == 0:
            return values
        lo, hi = float(values.min()), float(values.max())
        if hi - lo < 1e-8:
            return np.full_like(values, 0.5, dtype=np.float32)
        return (values - lo) / (hi - lo)

    def fuse(self, hits: list[RetrievalHit], alpha: float | None = None) -> list[RetrievalHit]:
        """Compute final_score = α * dense_prior + (1-α) * normalised_reranker_score."""
        if not hits:
            return []
        alpha = self.config.alpha if alpha is None else float(alpha)
        rr = self._minmax(
            np.asarray([x.reranker_score or 0.0 for x in hits], dtype=np.float32)
        )
        max_rank = max(1, len(hits) - 1)
        for i, hit in enumerate(hits):
            dense_prior = 1.0 - i / max_rank   # position-based dense prior
            hit.reranker_score = hit.reranker_score  # already set
            final = alpha * dense_prior + (1.0 - alpha) * float(rr[i])
            # store final_score back on the hit (duck-typed extra field)
            object.__setattr__(hit, "final_score", final) if False else setattr(hit, "final_score", final)  # noqa
        hits.sort(key=lambda x: (-float(getattr(x, "final_score", 0.0)), x.document_id))
        return hits

    # ------------------------------------------------------------------
    # Public retrieve API
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        """Run the full pipeline and return a structured result dict."""
        top_k = top_k or self.config.final_k
        t0 = time.perf_counter()

        dense = self.dense_search(query)
        t1 = time.perf_counter()

        bm25 = self.bm25_search(query)
        t2 = time.perf_counter()

        pool = self.dense_preserving_union(dense, bm25, self.config.rerank_candidates)
        t3 = time.perf_counter()

        if self.reranker is not None:
            scores = self.reranker.score(
                query, pool, self.config.rerank_candidates, self.config.rerank_max_chars
            )
            for hit, score in zip(pool, scores):
                hit.reranker_score = float(score)
            final = self.fuse(pool)[:top_k]
        else:
            final = pool[:top_k]

        t4 = time.perf_counter()

        latency = {
            "dense_ms": (t1 - t0) * 1000,
            "bm25_ms": (t2 - t1) * 1000,
            "candidate_ms": (t3 - t2) * 1000,
            "rerank_ms": (t4 - t3) * 1000,
            "end_to_end_ms": (t4 - t0) * 1000,
        }
        return {
            "query": query,
            "results": [x.as_dict() for x in final],
            "dense": [x.as_dict() for x in dense],
            "bm25": [x.as_dict() for x in bm25],
            "candidate_pool": [x.as_dict() for x in pool],
            "latency_ms": latency,
        }


__all__ = ["HybridRetriever", "_metadata_text", "_lexical_text"]
