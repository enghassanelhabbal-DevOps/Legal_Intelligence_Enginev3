"""dense.py — BGE-M3 dense encoder and FAISS index wrappers.

Extracted from legal_rag_engine.py (DenseEncoder, DenseIndex classes).
GPU memory policy (ARCHITECTURE_CONTRACT.md §Hardware):
  - FAISS index lives on CPU always
  - Encoder model on GPU only during encode; caller is responsible for offload
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from src.legal_ai.core.logging import get_logger
from src.legal_ai.runtime.adaptive_batch import AdaptiveBatchState, initial_state
from src.legal_ai.runtime.execution import ModelConcurrencyGate
from src.legal_ai.runtime.torch_adaptive_batch import run_batch_with_adaptive_policy

LOGGER = get_logger(__name__)


class DenseEncoder:
    """Thin wrapper around SentenceTransformer for BGE-M3.

    Keeps the model on the requested device; for the M2200 (4 GB VRAM) keep
    only ONE transformer loaded at a time (encoder or reranker, not both).
    """

    def __init__(
        self,
        model_name: str,
        device: str,
        dtype: torch.dtype,
        max_seq_length: int = 1024,
        max_concurrency: int = 1,
    ) -> None:
        LOGGER.info("Loading dense model: %s (device=%s, dtype=%s)", model_name, device, dtype)
        self.model = SentenceTransformer(model_name, device=device)
        self.model.max_seq_length = max_seq_length
        if device.startswith("cuda") and dtype == torch.float16:
            self.model.half()
        self.device = device
        self.dtype = dtype
        # Adaptive batch state (runtime.adaptive_batch): re-initialized per
        # `encode_documents` call whenever the caller's requested ceiling
        # changes, otherwise persisted across calls so a batch size that
        # had to shrink due to OOM can recover back toward the ceiling over
        # the encoder's lifetime rather than re-starting from scratch every
        # call.
        self._batch_state: AdaptiveBatchState | None = None
        # Bounds concurrent forward passes into THIS model object
        # (runtime.execution.ModelConcurrencyGate) — independent from how
        # many concurrent API requests BoundedExecutor admits. Sized from
        # ResourceBudget.max_model_concurrency via ResolvedRuntimePlan
        # (conservatively 1 by default); never a value this class invents.
        self._concurrency_gate = ModelConcurrencyGate(max_concurrency)

    # ------------------------------------------------------------------

    def encode_documents(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Batch-encode a list of document texts. Returns float32 array (N, dim).

        `batch_size` is the CEILING for this call — the deterministic
        adaptive batch policy (`runtime.adaptive_batch`, wired via
        `runtime.torch_adaptive_batch`) may run at a smaller size and
        retry (bounded) if an out-of-memory condition is hit, but it will
        never encode above `batch_size`. Encoding is a pure function of
        the input texts — grouping them into smaller batches changes
        nothing about the returned embeddings, only how much memory a
        single forward pass uses, so this cannot affect retrieval
        scoring/ranking.
        """
        if self._batch_state is None or self._batch_state.ceiling != batch_size:
            self._batch_state = initial_state(ceiling=batch_size)

        def _encode_at(size: int) -> np.ndarray:
            _autocast = (
                torch.autocast(device_type="cuda", dtype=self.dtype)
                if self.device.startswith("cuda") and self.dtype == torch.bfloat16
                else nullcontext()
            )
            with torch.inference_mode(), _autocast:
                embeddings = self.model.encode(
                    list(texts),
                    batch_size=size,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=True,
                )
            return np.asarray(embeddings, dtype=np.float32)

        with self._concurrency_gate:
            result, self._batch_state = run_batch_with_adaptive_policy(
                self._batch_state, _encode_at
            )
        return result

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query. Returns float32 array (1, dim)."""
        _autocast = (
            torch.autocast(device_type="cuda", dtype=self.dtype)
            if self.device.startswith("cuda") and self.dtype == torch.bfloat16
            else nullcontext()
        )
        with self._concurrency_gate, torch.inference_mode(), _autocast:
            embedding = self.model.encode(
                [query],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return np.asarray(embedding, dtype=np.float32)


class DenseIndex:
    """FAISS flat inner-product index (CPU).

    Inner-product on L2-normalised vectors == cosine similarity.
    FAISS stays on CPU per the hardware policy.
    """

    def __init__(self, embeddings: np.ndarray) -> None:
        embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.ndim != 2:
            raise ValueError("Embeddings must be a 2D array.")
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    def search(self, query_embedding: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (scores, indices) arrays of shape (1, k)."""
        return self.index.search(query_embedding, min(k, self.index.ntotal))

    def save(self, path: Path) -> None:
        faiss.write_index(self.index, str(path))

    @staticmethod
    def load(path: Path) -> DenseIndex:
        obj = object.__new__(DenseIndex)
        obj.index = faiss.read_index(str(path))
        return obj


__all__ = ["DenseEncoder", "DenseIndex"]
