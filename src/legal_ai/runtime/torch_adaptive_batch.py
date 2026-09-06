"""torch_adaptive_batch.py — torch-aware glue between the deterministic
`runtime.adaptive_batch` policy and real torch/CUDA/CPU out-of-memory
exceptions.

Deliberately kept OUT of `runtime/__init__.py`'s exports and separate from
`runtime.adaptive_batch` (which is intentionally torch-free and part of the
Stage 1/2 "governed modules" CI gate — see `.github/workflows/ci.yml` /
DR-032). Importing this module pulls in torch, so only
`src/legal_ai/retrieval/dense.py` and `src/legal_ai/reranking/cross_encoder.py`
import it directly — both already hard-require torch, so this adds no new
exposure to the lightweight/remote profile (DR-030).
"""

from __future__ import annotations

from collections.abc import Callable

import torch

from src.legal_ai.core.logging import get_logger
from src.legal_ai.runtime.adaptive_batch import AdaptiveBatchState, on_out_of_memory, on_success
from src.legal_ai.runtime.faults import FaultClass, recovery_policy_for

LOGGER = get_logger(__name__)


def is_out_of_memory_error(exc: BaseException) -> bool:
    """Classify an exception as an out-of-memory condition.

    Checks, in order: CPU `MemoryError`; torch's dedicated
    `torch.cuda.OutOfMemoryError` (torch >= 2.x); a message-based fallback
    for the plain `RuntimeError` some torch/driver versions still raise for
    CUDA OOM. The message check is last and narrow (exact substring) so it
    never accidentally swallows an unrelated `RuntimeError`.
    """
    if isinstance(exc, MemoryError):
        return True
    cuda_oom_type = getattr(torch.cuda, "OutOfMemoryError", None)
    if cuda_oom_type is not None and isinstance(exc, cuda_oom_type):
        return True
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


def run_batch_with_adaptive_policy[T](
    state: AdaptiveBatchState, call: Callable[[int], T]
) -> tuple[T, AdaptiveBatchState]:
    """Call `call(batch_size)` starting at `state.current_batch_size`.

    On an OOM-classified exception: deterministically halve the batch size
    (`runtime.adaptive_batch.on_out_of_memory` — no randomness, bounded at
    `state.floor`) and retry, bounded by the `OUT_OF_MEMORY` fault class's
    registered `RecoveryPolicy.max_attempts` (`runtime.faults`, currently
    1) — this is never an unbounded retry loop
    (RESOURCE_RELIABILITY_SPEC.md §10). If the batch size is already
    exhausted (at `floor` and still failing) or attempts are used up, the
    exception is re-raised rather than silently swallowed.

    On success: records it via `on_success()` so the batch size can
    recover back toward its original ceiling over subsequent calls, and
    empties the CUDA cache between a failed attempt and the next one so
    the retry has a real chance of succeeding at the smaller size rather
    than immediately re-hitting the same fragmented allocation.

    This never changes what `call` computes for a given batch size — only
    how many attempts, at what size, are made. Retrieval scoring/fusion/
    ranking values are identical to calling `call` directly with a fixed
    batch size that happens to fit in memory.
    """
    max_attempts = recovery_policy_for(FaultClass.OUT_OF_MEMORY).max_attempts
    current_state = state
    attempts_used = 0

    while True:
        try:
            result = call(current_state.current_batch_size)
        except Exception as exc:  # noqa: BLE001 - re-raised below unless OOM and still bounded
            if not is_out_of_memory_error(exc):
                raise
            attempts_used += 1
            LOGGER.warning(
                "OOM at batch_size=%d (attempt %d/%d); stepping batch size down deterministically.",
                current_state.current_batch_size, attempts_used, max_attempts,
            )
            current_state = on_out_of_memory(current_state)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if current_state.exhausted or attempts_used > max_attempts:
                LOGGER.error(
                    "OUT_OF_MEMORY recovery exhausted after %d attempt(s) at floor "
                    "batch_size=%d; re-raising.",
                    attempts_used, current_state.current_batch_size,
                )
                raise
            continue
        else:
            return result, on_success(current_state)


__all__ = ["is_out_of_memory_error", "run_batch_with_adaptive_policy"]
