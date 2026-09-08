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


class _WrongShapeSentenceTransformer(_FlakySentenceTransformer):
    """Simulates a programming/config bug (invalid tensor shape), NOT a
    resource condition — must propagate immediately, never be retried."""

    def encode(self, texts, batch_size, **kwargs):
        self.calls.append(batch_size)
        raise RuntimeError("mat1 and mat2 shapes cannot be multiplied (3x4 and 5x6)")


class _ValueErrorSentenceTransformer(_FlakySentenceTransformer):
    def encode(self, texts, batch_size, **kwargs):
        self.calls.append(batch_size)
        raise ValueError("invalid model configuration: unknown pooling mode")


def test_encode_documents_propagates_non_oom_runtime_error_immediately():
    """Item 18: only resource/OOM conditions may trigger adaptive
    step-down. A RuntimeError with an unrelated message (shape mismatch —
    a real programming bug) must propagate on the FIRST attempt, with the
    batch size never touched."""
    with patch("src.legal_ai.retrieval.dense.SentenceTransformer", _WrongShapeSentenceTransformer):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        with pytest.raises(RuntimeError, match="shapes cannot be multiplied"):
            encoder.encode_documents(["x"], batch_size=32)
        # Exactly one call, at the original ceiling — no retry, no step-down.
        assert encoder.model.calls == [32]
        assert encoder._batch_state.current_batch_size == 32
        assert encoder._batch_state.consecutive_failures == 0


def test_encode_documents_propagates_value_error_immediately_never_classified_as_oom():
    """A ValueError (invalid config, not a resource condition) must never
    be caught by the adaptive-batch retry path at all — it isn't even a
    RuntimeError/MemoryError, so is_out_of_memory_error() must never be
    asked about it in a way that could swallow it."""
    with patch(
        "src.legal_ai.retrieval.dense.SentenceTransformer", _ValueErrorSentenceTransformer
    ):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        with pytest.raises(ValueError, match="invalid model configuration"):
            encoder.encode_documents(["x"], batch_size=32)
        assert encoder.model.calls == [32]


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad config"),
        TypeError("unexpected keyword argument"),
        RuntimeError("size mismatch, m1: [3 x 4], m2: [5 x 6]"),
        RuntimeError("index out of range in self"),
        KeyError("missing_field"),
    ],
)
def test_is_out_of_memory_error_rejects_non_resource_exceptions(exc):
    from src.legal_ai.runtime.torch_adaptive_batch import is_out_of_memory_error

    assert is_out_of_memory_error(exc) is False


@pytest.mark.parametrize(
    "exc",
    [
        MemoryError(),
        RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"),
        RuntimeError("OUT OF MEMORY on device 0"),  # case-insensitive match
    ],
)
def test_is_out_of_memory_error_accepts_real_oom_signals(exc):
    from src.legal_ai.runtime.torch_adaptive_batch import is_out_of_memory_error

    assert is_out_of_memory_error(exc) is True


def test_is_out_of_memory_error_accepts_real_torch_cuda_oom_type():
    from src.legal_ai.runtime.torch_adaptive_batch import is_out_of_memory_error

    assert is_out_of_memory_error(torch.OutOfMemoryError("simulated")) is True


class _OrderPreservingSentenceTransformer:
    """Encodes texts to their own index value so a caller can directly
    verify embedding[i] still corresponds to texts[i] regardless of how
    many times the call was retried at a smaller batch size, or how many
    texts remain in a non-even final batch."""

    def __init__(self, model_name: str, device: str) -> None:
        self.max_seq_length = None
        self.calls: list[int] = []
        self.oom_budget = 0  # number of OOMs to simulate before succeeding

    def encode(self, texts, batch_size, **kwargs):
        self.calls.append(batch_size)
        if len(self.calls) <= self.oom_budget:
            raise RuntimeError("CUDA out of memory. Tried to allocate 1.00 GiB")
        return np.array([[float(i)] for i in range(len(texts))], dtype=np.float32)


@pytest.mark.parametrize(
    "n_texts,oom_budget,ceiling",
    [
        (5, 0, 32),   # single batch, no retry
        (5, 1, 32),   # one OOM retry (the OUT_OF_MEMORY policy's bounded max: 1 retry)
        (7, 0, 3),    # non-even final batch vs. ceiling (grouping is internal to encode())
        (1, 0, 1),    # batch_size=1
    ],
)
def test_output_order_and_count_preserved_across_batch_retry_scenarios(
    n_texts, oom_budget, ceiling
):
    texts = [f"text-{i}" for i in range(n_texts)]
    with patch(
        "src.legal_ai.retrieval.dense.SentenceTransformer", _OrderPreservingSentenceTransformer
    ):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        encoder.model.oom_budget = oom_budget
        embeddings = encoder.encode_documents(texts, batch_size=ceiling)

    assert embeddings.shape[0] == n_texts  # output count preserved
    for i in range(n_texts):
        assert embeddings[i][0] == float(i)  # embedding[i] corresponds to texts[i]


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
