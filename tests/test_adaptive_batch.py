from __future__ import annotations

import pytest

from src.legal_ai.runtime.adaptive_batch import (
    RECOVERY_STREAK_REQUIRED,
    initial_state,
    on_out_of_memory,
    on_success,
)


def test_initial_state_starts_at_ceiling():
    state = initial_state(ceiling=64)
    assert state.current_batch_size == 64
    assert state.floor == 1
    assert not state.exhausted


def test_ceiling_below_floor_rejected():
    with pytest.raises(ValueError):
        initial_state(ceiling=1, floor=4)


def test_out_of_memory_halves_deterministically():
    state = initial_state(ceiling=64)
    state = on_out_of_memory(state)
    assert state.current_batch_size == 32
    state = on_out_of_memory(state)
    assert state.current_batch_size == 16
    state = on_out_of_memory(state)
    assert state.current_batch_size == 8


def test_never_shrinks_below_floor():
    state = initial_state(ceiling=8, floor=4)
    state = on_out_of_memory(state)  # 8 -> 4
    assert state.current_batch_size == 4
    state = on_out_of_memory(state)  # already at floor
    assert state.current_batch_size == 4
    assert state.exhausted is True


def test_exhausted_flag_set_only_when_failing_at_floor():
    state = initial_state(ceiling=2, floor=1)
    state = on_out_of_memory(state)  # 2 -> 1
    assert state.current_batch_size == 1
    assert state.exhausted is False
    state = on_out_of_memory(state)  # fails again at floor
    assert state.exhausted is True


def test_recovery_requires_streak_not_single_success():
    state = initial_state(ceiling=32)
    state = on_out_of_memory(state)  # -> 16
    for _ in range(RECOVERY_STREAK_REQUIRED - 1):
        state = on_success(state)
        assert state.current_batch_size == 16  # not yet — streak incomplete
    state = on_success(state)  # completes the streak
    assert state.current_batch_size == 32


def test_recovery_never_exceeds_ceiling():
    state = initial_state(ceiling=10)
    state = on_out_of_memory(state)  # 10 -> 5
    for _ in range(RECOVERY_STREAK_REQUIRED):
        state = on_success(state)
    assert state.current_batch_size == 10  # doubled from 5 -> 10, capped at ceiling
    for _ in range(RECOVERY_STREAK_REQUIRED):
        state = on_success(state)
    assert state.current_batch_size == 10  # already at ceiling, stays there


def test_success_after_exhaustion_clears_exhausted_flag():
    state = initial_state(ceiling=2, floor=1)
    state = on_out_of_memory(state)  # -> 1
    state = on_out_of_memory(state)  # exhausted at floor
    assert state.exhausted is True
    state = on_success(state)
    assert state.exhausted is False
    assert state.current_batch_size == 1


def test_success_resets_failure_counter():
    state = initial_state(ceiling=32)
    state = on_out_of_memory(state)
    assert state.consecutive_failures == 1
    state = on_success(state)
    assert state.consecutive_failures == 0


def test_replaying_same_outcome_sequence_is_fully_deterministic():
    """No randomness, no timing input: the same sequence of outcomes
    against the same starting ceiling/floor must always produce the exact
    same sequence of states."""
    outcomes = ["oom", "oom", "success", "success", "success", "oom", "success"]

    def replay():
        state = initial_state(ceiling=64, floor=2)
        trace = [state.current_batch_size]
        for outcome in outcomes:
            state = on_out_of_memory(state) if outcome == "oom" else on_success(state)
            trace.append(state.current_batch_size)
        return trace

    assert replay() == replay()
