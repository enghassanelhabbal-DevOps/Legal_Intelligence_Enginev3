"""cross_encoder.py — BGE Reranker v2-m3 wrapper using batch inference.

Extracted from legal_rag_engine.py (Reranker class).
ARCHITECTURE_CONTRACT.md §ML rules: reranking must use batch inference.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import torch
from sentence_transformers import CrossEncoder

from src.legal_ai.core.logging import get_logger
from src.legal_ai.core.models import RetrievalHit

LOGGER = get_logger(__name__)



class Reranker:
    """BGE cross-encoder reranker with batch inference.

    Memory note (M2200 / 4 GB VRAM): load/unload the reranker explicitly
    around the reranking call if you need to keep the dense encoder in memory.
    """

    def __init__(
        self,
        model_name: str,
        device: str,
        dtype: torch.dtype,
        max_seq_length: int = 1024,
        compile_model: bool = False,
    ) -> None:
        LOGGER.info("Loading reranker: %s (device=%s)", model_name, device)
        model_kwargs: dict = {}
        if device.startswith("cuda"):
            model_kwargs["torch_dtype"] = dtype
        self.model = CrossEncoder(
            model_name,
            device=device,
            max_length=max_seq_length,
            model_kwargs=model_kwargs,
        )
        self.device = device

        if compile_model and device.startswith("cuda") and hasattr(self.model, "compile"):
            try:
                self.model.compile(dynamic=True)
                LOGGER.info("CrossEncoder torch.compile enabled.")
            except Exception as exc:
                LOGGER.warning("torch.compile unavailable for reranker: %s", exc)

    def score(
        self,
        query: str,
        candidates: Sequence[RetrievalHit],
        batch_size: int,
        max_chars: int,
    ) -> np.ndarray:
        """Return a float32 array of shape (len(candidates),) with raw scores."""
        pairs = [
            [query, f"{c.law_name}: {c.text}"[:max_chars]]
            for c in candidates
        ]
        with torch.inference_mode():
            scores = self.model.predict(
                pairs,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                apply_softmax=False,
            )
        return np.asarray(scores, dtype=np.float32).reshape(-1)

    def unload(self) -> None:
        """Move model to CPU and release GPU memory."""
        try:
            self.model.model.to("cpu")
            del self.model
        except Exception:
            pass
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


__all__ = ["Reranker"]
