from __future__ import annotations

import pytest

from src.legal_ai.runtime.budgets import budget_for_profile
from src.legal_ai.runtime.profiles import ExecutionProfile


@pytest.mark.parametrize("profile", list(ExecutionProfile))
def test_every_profile_has_a_registered_bounded_budget(profile):
    budget = budget_for_profile(profile)
    # RESOURCE_RELIABILITY_SPEC.md §4/§10: every field must be a concrete,
    # finite, positive-or-zero bound — never unbounded/negative.
    assert budget.max_workers >= 1
    assert budget.max_queue_size >= 1
    assert budget.dense_batch_size >= 1
    assert budget.rerank_batch_size >= 0  # 0 == "off by policy" (CPU-minimal)
    assert budget.max_seq_length >= 1
    assert budget.max_candidates >= 1
    assert budget.max_retries >= 0
    assert budget.request_timeout_seconds > 0
    assert budget.memory_target_bytes > 0


def test_cpu_minimal_disables_reranker_by_policy():
    budget = budget_for_profile(ExecutionProfile.CPU_MINIMAL)
    assert budget.rerank_batch_size == 0


def test_budgets_are_frozen_and_immutable():
    budget = budget_for_profile(ExecutionProfile.BALANCED)
    with pytest.raises(AttributeError):
        budget.max_workers = 999  # type: ignore[misc]
