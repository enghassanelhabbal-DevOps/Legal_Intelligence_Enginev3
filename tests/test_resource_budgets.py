from __future__ import annotations

import pytest

from src.legal_ai.runtime.budgets import budget_for_profile
from src.legal_ai.runtime.cpu_topology import ContainerRuntime, CPUTopology
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


def test_no_cpu_topology_keeps_static_baseline_workers():
    """Back-compat: existing callers that don't pass hardware info get the
    same deterministic values as before topology-awareness was added."""
    assert budget_for_profile(ExecutionProfile.BALANCED).max_workers == 4
    assert budget_for_profile(ExecutionProfile.ACCELERATED).max_workers == 6


def test_cpu_minimal_stays_pinned_at_one_worker_regardless_of_core_count():
    """CPU_MINIMAL is chosen because hardware IS constrained; it must never
    scale workers up even if cpu_topology somehow reports many cores."""
    ample = CPUTopology(
        logical_cores_host=64, physical_cores_host=32, affinity_cores=64,
        cgroup_quota_cores=None, container_runtime=ContainerRuntime.NONE,
        hyperthreading_likely=True, effective_cores=64, effective_cores_source="host_logical",
    )
    budget = budget_for_profile(ExecutionProfile.CPU_MINIMAL, cpu_topology=ample)
    assert budget.max_workers == 1


def test_balanced_scales_workers_down_on_a_constrained_container():
    constrained = CPUTopology(
        logical_cores_host=32, physical_cores_host=16, affinity_cores=None,
        cgroup_quota_cores=1.0, container_runtime=ContainerRuntime.KUBERNETES,
        hyperthreading_likely=True, effective_cores=1, effective_cores_source="cgroup_quota",
    )
    budget = budget_for_profile(ExecutionProfile.BALANCED, cpu_topology=constrained)
    assert budget.max_workers == 2  # clamped to the profile's floor, not 0/1


def test_balanced_scales_workers_up_but_stays_within_clamp_ceiling():
    ample = CPUTopology(
        logical_cores_host=128, physical_cores_host=64, affinity_cores=128,
        cgroup_quota_cores=None, container_runtime=ContainerRuntime.NONE,
        hyperthreading_likely=True, effective_cores=128, effective_cores_source="host_logical",
    )
    budget = budget_for_profile(ExecutionProfile.BALANCED, cpu_topology=ample)
    assert budget.max_workers == 8  # clamp ceiling — never unbounded (§4/§10)


def test_remote_llm_allows_more_workers_than_cores_but_still_bounded():
    """I/O-bound: allowed to exceed effective_cores, but the ceiling is
    still a concrete finite number, never unlimited."""
    modest = CPUTopology(
        logical_cores_host=4, physical_cores_host=4, affinity_cores=4,
        cgroup_quota_cores=None, container_runtime=ContainerRuntime.NONE,
        hyperthreading_likely=False, effective_cores=4, effective_cores_source="host_logical",
    )
    budget = budget_for_profile(ExecutionProfile.REMOTE_LLM, cpu_topology=modest)
    assert budget.max_workers == 8  # 4 * multiplier(2), within [4, 16]

    tiny = CPUTopology(
        logical_cores_host=1, physical_cores_host=1, affinity_cores=1,
        cgroup_quota_cores=None, container_runtime=ContainerRuntime.NONE,
        hyperthreading_likely=False, effective_cores=1, effective_cores_source="affinity_mask",
    )
    tiny_budget = budget_for_profile(ExecutionProfile.REMOTE_LLM, cpu_topology=tiny)
    assert tiny_budget.max_workers == 4  # floored to the profile's minimum


def test_scaled_budget_only_changes_max_workers_other_fields_untouched():
    constrained = CPUTopology(
        logical_cores_host=2, physical_cores_host=2, affinity_cores=2,
        cgroup_quota_cores=None, container_runtime=ContainerRuntime.NONE,
        hyperthreading_likely=False, effective_cores=2, effective_cores_source="host_logical",
    )
    static = budget_for_profile(ExecutionProfile.BALANCED)
    scaled = budget_for_profile(ExecutionProfile.BALANCED, cpu_topology=constrained)
    assert scaled.max_queue_size == static.max_queue_size
    assert scaled.dense_batch_size == static.dense_batch_size
    assert scaled.request_timeout_seconds == static.request_timeout_seconds
