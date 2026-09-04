"""adaptive_batch.py — deterministic adaptive batch-size policy.

`runtime.faults` already declares that an `OUT_OF_MEMORY` fault recovers
via `RecoveryAction.REDUCE_BATCH_AND_RETRY` (max_attempts=1), but that
policy only says a retry is bounded to one attempt — it does not say what
batch size to retry *with*. This module supplies that: a pure, stateless
transition function from one `AdaptiveBatchState` to the next.

Deterministic by construction:
  - No randomness anywhere (no `random`, no jitter).
  - No wall-clock or timing input — decisions depend only on the state and
    the outcome (success/OOM) passed in, so replaying the same sequence of
    outcomes against the same starting state always produces the same
    sequence of batch sizes (see `tests/test_adaptive_batch.py`'s replay
    test).
  - Monotonic and bounded: `on_out_of_memory` only ever shrinks toward
    `floor` (never below it); `on_success` only ever grows back toward
    `ceiling` (never above it, and never before `floor`). `ceiling` is set
    once at `initial_state()` from `ResourceBudget.dense_batch_size` /
    `rerank_batch_size` — this policy never exceeds what
    `budget_for_profile()` already decided was safe for the resolved
    execution profile; it only adapts *downward* within that ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# Consecutive successes required at the current (possibly-reduced) batch
# size before stepping back up — deterministic hysteresis so a single
# lucky success doesn't immediately re-trigger the same OOM.
RECOVERY_STREAK_REQUIRED = 3
RECOVERY_STEP_MULTIPLIER = 2  # doubles back up, mirroring the halving-down step


@dataclass(frozen=True)
class AdaptiveBatchState:
    current_batch_size: int
    ceiling: int
    floor: int
    consecutive_failures: int
    consecutive_successes: int
    exhausted: bool  # True once batch size is already at `floor` and still failed


def initial_state(ceiling: int, floor: int = 1) -> AdaptiveBatchState:
    """Start a new adaptive-batch policy. `ceiling` should come from the
    resolved `ResourceBudget` (`dense_batch_size` or `rerank_batch_size`)
    for the current execution profile — never a value this policy invents
    on its own.
    """
    if floor < 1:
        raise ValueError(f"floor must be >= 1, got {floor}")
    if ceiling < floor:
        raise ValueError(f"ceiling ({ceiling}) must be >= floor ({floor})")
    return AdaptiveBatchState(
        current_batch_size=ceiling,
        ceiling=ceiling,
        floor=floor,
        consecutive_failures=0,
        consecutive_successes=0,
        exhausted=False,
    )


def on_out_of_memory(state: AdaptiveBatchState) -> AdaptiveBatchState:
    """Deterministic halving on OOM: floor-division by 2, clamped at
    `state.floor`. If already at `floor` and it still failed, mark
    `exhausted=True` — the caller's `RecoveryPolicy` for `OUT_OF_MEMORY`
    (max_attempts=1) should stop retrying and surface the failure as a
    `FailureEvent` rather than loop indefinitely.
    """
    if state.current_batch_size <= state.floor:
        return replace(state, exhausted=True, consecutive_failures=state.consecutive_failures + 1,
                        consecutive_successes=0)
    new_size = max(state.floor, state.current_batch_size // 2)
    return replace(
        state,
        current_batch_size=new_size,
        consecutive_failures=state.consecutive_failures + 1,
        consecutive_successes=0,
        exhausted=False,
    )


def on_success(state: AdaptiveBatchState) -> AdaptiveBatchState:
    """Record a successful batch at the current size. After
    `RECOVERY_STREAK_REQUIRED` consecutive successes, step the batch size
    back up toward `ceiling` (never past it).
    """
    if state.exhausted:
        # A retry at floor size succeeded after all — clear exhaustion,
        # stay at floor, start counting a fresh recovery streak.
        return replace(state, consecutive_failures=0, consecutive_successes=1, exhausted=False)

    successes = state.consecutive_successes + 1
    if successes >= RECOVERY_STREAK_REQUIRED and state.current_batch_size < state.ceiling:
        new_size = min(state.ceiling, state.current_batch_size * RECOVERY_STEP_MULTIPLIER)
        return replace(
            state,
            current_batch_size=new_size,
            consecutive_failures=0,
            consecutive_successes=0,
        )
    return replace(state, consecutive_failures=0, consecutive_successes=successes)


__all__ = [
    "AdaptiveBatchState",
    "initial_state",
    "on_out_of_memory",
    "on_success",
    "RECOVERY_STREAK_REQUIRED",
    "RECOVERY_STEP_MULTIPLIER",
]
