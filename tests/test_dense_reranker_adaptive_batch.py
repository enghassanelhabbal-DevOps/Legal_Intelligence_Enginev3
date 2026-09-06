"""Integration tests for the real dense-encoding and reranking batch paths.

Requires the `dense` extra (torch, sentence-transformers) — excluded from
the lightweight CPU-safe CI tier for the same reason `tests/test_retrieval.py`
is (faiss/torch not installed there). Verified locally in a sandbox with the
`dense` extra installed; see the delivery report for exact pass/exclusion
counts.

The underlying `SentenceTransformer`/`CrossEncoder` model classes are
replaced with small deterministic fakes (no network access, no real model
weights) that simulate exactly one out-of-memory failure at the caller's
requested batch size, then succeed at a smaller size — this exercises the
REAL `DenseEncoder.encode_documents()` / `Reranker.score()` code paths
end-to-end, not a reimplementation of them.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
import torch

from src.legal_ai.reranking.cross_encoder import Reranker
from src.legal_ai.retrieval.dense import DenseEncoder
from src.legal_ai.runtime import adaptive_batch


class _FlakySentenceTransformer:
    """Fakes SentenceTransformer.encode: OOMs once at the ceiling batch
    size, then returns a deterministic embedding depending only on text
    content (never on batch_size) — proves batch-size adaptation cannot
    change retrieval scoring."""

    def __init__(self, model_name: str, device: str) -> None:
        self.model_name = model_name
        self.device = device
        self.max_seq_length = None
        self.calls: list[int] = []

    def half(self) -> None:
        pass

    def encode(self, texts, batch_size, **kwargs):
        self.calls.append(batch_size)
        if len(self.calls) == 1:
            raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
        return np.array([[float(len(t)), 1.0] for t in texts], dtype=np.float32)


class _AlwaysOOMSentenceTransformer(_FlakySentenceTransformer):
    def encode(self, texts, batch_size, **kwargs):
        self.calls.append(batch_size)
        raise RuntimeError("CUDA out of memory. Tried to allocate 99.00 GiB")


class _FlakyCrossEncoder:
    def __init__(self, model_name: str, device: str, max_length: int, model_kwargs: dict) -> None:
        self.calls: list[int] = []

    def predict(self, pairs, batch_size, **kwargs):
        self.calls.append(batch_size)
        if len(self.calls) == 1:
            raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
        return np.array([float(len(p[1])) for p in pairs], dtype=np.float32)


def _make_hits(n: int):
    from src.legal_ai.core.models import RetrievalHit

    return [
        RetrievalHit(
            document_id=str(i), index=i, text=f"نص {i}" * 5, law_name="قانون", article_id=str(i)
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# DenseEncoder
# ---------------------------------------------------------------------------

def test_encode_documents_steps_down_deterministically_on_real_oom_and_preserves_values():
    with patch("src.legal_ai.retrieval.dense.SentenceTransformer", _FlakySentenceTransformer):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        texts = ["hello", "world", "قانون"]

        embeddings = encoder.encode_documents(texts, batch_size=32)

        # Stepped down exactly once (32 -> 16), matching adaptive_batch's
        # own halving rule exactly — not some ad hoc retry number.
        assert encoder.model.calls == [32, 16]
        # Values depend only on text content, not on which batch size
        # actually ran — retrieval scoring is unaffected by the retry.
        expected = np.array([[float(len(t)), 1.0] for t in texts], dtype=np.float32)
        np.testing.assert_array_equal(embeddings, expected)


def test_encode_documents_recovers_batch_size_after_repeated_successes():
    with patch("src.legal_ai.retrieval.dense.SentenceTransformer", _FlakySentenceTransformer):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        texts = ["a", "b"]

        encoder.encode_documents(texts, batch_size=32)  # 32 -> 16 (one OOM)
        assert encoder._batch_state.current_batch_size == 16

        for _ in range(adaptive_batch.RECOVERY_STREAK_REQUIRED):
            encoder.encode_documents(texts, batch_size=32)
        assert encoder._batch_state.current_batch_size == 32  # recovered to the original ceiling


def test_encode_documents_bounded_retry_reraises_when_exhausted():
    """OUT_OF_MEMORY's registered RecoveryPolicy allows exactly 1 retry —
    an encoder that OOMs at every batch size down to the floor must
    re-raise rather than loop forever."""
    with patch("src.legal_ai.retrieval.dense.SentenceTransformer", _AlwaysOOMSentenceTransformer):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        with pytest.raises(RuntimeError, match="out of memory"):
            encoder.encode_documents(["x"], batch_size=2)
        # 2 -> 1 (one deterministic step-down attempt), then re-raised —
        # never an unbounded number of calls.
        assert encoder.model.calls == [2, 1]


def test_encode_documents_bypass_detection():
    """Fails-if-bypassed guard (item 7): if a future refactor makes
    encode_documents() call self.model.encode() directly instead of
    through runtime.torch_adaptive_batch.run_batch_with_adaptive_policy,
    this test must fail."""
    with patch("src.legal_ai.retrieval.dense.SentenceTransformer", _FlakySentenceTransformer):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        with patch(
            "src.legal_ai.retrieval.dense.run_batch_with_adaptive_policy",
            side_effect=RuntimeError("adaptive policy bypass detected"),
        ) as mocked:
            with pytest.raises(RuntimeError, match="adaptive policy bypass detected"):
                encoder.encode_documents(["x"], batch_size=8)
            assert mocked.called


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------

def test_reranker_score_steps_down_deterministically_on_real_oom_and_preserves_values():
    with patch("src.legal_ai.reranking.cross_encoder.CrossEncoder", _FlakyCrossEncoder):
        reranker = Reranker("fake-reranker", device="cpu", dtype=torch.float32)
        hits = _make_hits(3)

        scores = reranker.score("query", hits, batch_size=16, max_chars=100)

        assert reranker.model.calls == [16, 8]
        pairs_texts = [f"{h.law_name}: {h.text}"[:100] for h in hits]
        expected = np.array([float(len(t)) for t in pairs_texts], dtype=np.float32)
        np.testing.assert_array_equal(scores, expected)


def test_reranker_score_bypass_detection():
    with patch("src.legal_ai.reranking.cross_encoder.CrossEncoder", _FlakyCrossEncoder):
        reranker = Reranker("fake-reranker", device="cpu", dtype=torch.float32)
        with patch(
            "src.legal_ai.reranking.cross_encoder.run_batch_with_adaptive_policy",
            side_effect=RuntimeError("adaptive policy bypass detected"),
        ) as mocked:
            with pytest.raises(RuntimeError, match="adaptive policy bypass detected"):
                reranker.score("q", _make_hits(2), batch_size=8, max_chars=50)
            assert mocked.called
