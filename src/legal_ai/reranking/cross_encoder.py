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
from src.legal_ai.runtime.adaptive_batch import AdaptiveBatchState, initial_state
from src.legal_ai.runtime.execution import ModelConcurrencyGate
from src.legal_ai.runtime.torch_adaptive_batch import run_batch_with_adaptive_policy

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
        max_concurrency: int = 1,
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

        # See DenseEncoder._batch_state — same deterministic adaptive-batch
        # pattern (runtime.adaptive_batch / runtime.torch_adaptive_batch),
        # persisted across score() calls on this instance.
        self._batch_state: AdaptiveBatchState | None = None
        # See DenseEncoder._concurrency_gate — bounds concurrent forward
        # passes into THIS reranker object, independent from request
        # admission concurrency.
        self._concurrency_gate = ModelConcurrencyGate(max_concurrency)

    def score(
        self,
        query: str,
        candidates: Sequence[RetrievalHit],
        batch_size: int,
        max_chars: int,
    ) -> np.ndarray:
        """Return a float32 array of shape (len(candidates),) with raw scores.

        `batch_size` is the CEILING for this call — see
        `DenseEncoder.encode_documents`'s docstring for why stepping this
        down on OOM cannot change the returned scores, only how much
        memory a single forward pass uses.
        """
        pairs = [
            [query, f"{c.law_name}: {c.text}"[:max_chars]]
            for c in candidates
        ]
        if self._batch_state is None or self._batch_state.ceiling != batch_size:
            self._batch_state = initial_state(ceiling=batch_size)

        def _score_at(size: int) -> np.ndarray:
            with torch.inference_mode():
                scores = self.model.predict(
                    pairs,
                    batch_size=size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    apply_softmax=False,
                )
            return np.asarray(scores, dtype=np.float32).reshape(-1)

        with self._concurrency_gate:
            result, self._batch_state = run_batch_with_adaptive_policy(self._batch_state, _score_at)
        return result

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
