"""Tests proving `ModelConcurrencyGate` actually prevents simultaneous
entry into a single model object's forward pass, independent of how many
API requests `BoundedExecutor` admits concurrently.

Requires the `dense` extra (torch/sentence-transformers) — part of the
dense CPU CI tier, excluded from the lightweight tier for the same reason
as `tests/test_retrieval.py` / `tests/test_dense_reranker_adaptive_batch.py`.

Uses instrumented fake models with `threading.Event`/counters — no real
GPU, no sleep-based flakiness beyond a bounded `join(timeout=...)`.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import numpy as np
import pytest
import torch

from src.legal_ai.reranking.cross_encoder import Reranker
from src.legal_ai.retrieval.dense import DenseEncoder
from src.legal_ai.runtime.execution import ModelConcurrencyGate


class _ConcurrencyDetectingSentenceTransformer:
    """Fakes SentenceTransformer.encode: records the maximum number of
    threads ever simultaneously inside encode() — the thing a
    ModelConcurrencyGate=1 policy must keep at 1."""

    def __init__(self, model_name: str, device: str) -> None:
        self.max_seq_length = None
        self._lock = threading.Lock()
        self._current = 0
        self.max_concurrent_seen = 0

    def encode(self, texts, batch_size, **kwargs):
        with self._lock:
            self._current += 1
            self.max_concurrent_seen = max(self.max_concurrent_seen, self._current)
        try:
            time.sleep(0.05)  # widen the window in which a race would show up
            return np.array([[float(len(t))] for t in texts], dtype=np.float32)
        finally:
            with self._lock:
                self._current -= 1


class _ConcurrencyDetectingCrossEncoder:
    def __init__(self, model_name: str, device: str, max_length: int, model_kwargs: dict) -> None:
        self._lock = threading.Lock()
        self._current = 0
        self.max_concurrent_seen = 0

    def predict(self, pairs, batch_size, **kwargs):
        with self._lock:
            self._current += 1
            self.max_concurrent_seen = max(self.max_concurrent_seen, self._current)
        try:
            time.sleep(0.05)
            return np.array([float(len(p[1])) for p in pairs], dtype=np.float32)
        finally:
            with self._lock:
                self._current -= 1


def test_model_concurrency_gate_serializes_two_threads_by_itself():
    """Unit-level proof of the primitive itself, independent of dense.py."""
    lock_free_counter = {"current": 0, "max_seen": 0}
    counter_lock = threading.Lock()
    gate = ModelConcurrencyGate(max_concurrency=1)

    def guarded_work():
        with gate:
            with counter_lock:
                lock_free_counter["current"] += 1
                lock_free_counter["max_seen"] = max(
                    lock_free_counter["max_seen"], lock_free_counter["current"]
                )
            time.sleep(0.05)
            with counter_lock:
                lock_free_counter["current"] -= 1

    threads = [threading.Thread(target=guarded_work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert lock_free_counter["max_seen"] == 1


def test_model_concurrency_gate_rejects_invalid_size():
    with pytest.raises(ValueError):
        ModelConcurrencyGate(max_concurrency=0)


def test_two_concurrent_dense_encode_calls_never_overlap_when_gate_is_one():
    """The real proof for Risk 3: two threads calling the SAME DenseEncoder
    instance's encode_documents() concurrently must never both be inside
    the underlying model's encode() at the same time when
    max_concurrency=1 — even though nothing here limits how many *threads*
    (i.e. admitted API requests) attempt the call."""
    with patch(
        "src.legal_ai.retrieval.dense.SentenceTransformer",
        _ConcurrencyDetectingSentenceTransformer,
    ):
        encoder = DenseEncoder(
            "fake-model", device="cpu", dtype=torch.float32, max_seq_length=64, max_concurrency=1
        )

        threads = [
            threading.Thread(target=encoder.encode_documents, args=(["a", "b"], 8))
            for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert encoder.model.max_concurrent_seen == 1


def test_two_concurrent_dense_encode_calls_can_overlap_when_gate_allows_it():
    """Negative control: with max_concurrency=2, two concurrent calls ARE
    allowed to overlap — proves the gate is actually load-bearing (a
    gate=1 test that would also pass with no gate at all would be
    worthless)."""
    with patch(
        "src.legal_ai.retrieval.dense.SentenceTransformer",
        _ConcurrencyDetectingSentenceTransformer,
    ):
        encoder = DenseEncoder(
            "fake-model", device="cpu", dtype=torch.float32, max_seq_length=64, max_concurrency=2
        )

        threads = [
            threading.Thread(target=encoder.encode_documents, args=(["a", "b"], 8))
            for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert encoder.model.max_concurrent_seen >= 2


def test_two_concurrent_reranker_score_calls_never_overlap_when_gate_is_one():
    from src.legal_ai.core.models import RetrievalHit

    hits = [RetrievalHit(document_id="1", index=0, text="نص", law_name="قانون", article_id="1")]

    with patch(
        "src.legal_ai.reranking.cross_encoder.CrossEncoder",
        _ConcurrencyDetectingCrossEncoder,
    ):
        reranker = Reranker(
            "fake-reranker", device="cpu", dtype=torch.float32, max_concurrency=1
        )

        threads = [
            threading.Thread(target=reranker.score, args=("q", hits, 8, 100)) for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert reranker.model.max_concurrent_seen == 1
