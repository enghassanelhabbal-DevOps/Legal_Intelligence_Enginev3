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
    ) -> None:
        LOGGER.info("Loading dense model: %s (device=%s, dtype=%s)", model_name, device, dtype)
        self.model = SentenceTransformer(model_name, device=device)
        self.model.max_seq_length = max_seq_length
        if device.startswith("cuda") and dtype == torch.float16:
            self.model.half()
        self.device = device
        self.dtype = dtype

    # ------------------------------------------------------------------

    def encode_documents(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Batch-encode a list of document texts.  Returns float32 array (N, dim)."""
        _autocast = (
            torch.autocast(device_type="cuda", dtype=self.dtype)
            if self.device.startswith("cuda") and self.dtype == torch.bfloat16
            else nullcontext()
        )
        with torch.inference_mode(), _autocast:
            embeddings = self.model.encode(
                list(texts),
                batch_size=batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=True,
            )
        return np.asarray(embeddings, dtype=np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query.  Returns float32 array (1, dim)."""
        _autocast = (
            torch.autocast(device_type="cuda", dtype=self.dtype)
            if self.device.startswith("cuda") and self.dtype == torch.bfloat16
            else nullcontext()
        )
        with torch.inference_mode(), _autocast:
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
