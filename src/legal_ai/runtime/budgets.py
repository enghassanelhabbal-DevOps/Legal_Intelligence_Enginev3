"""budgets.py — bounded resource budgets per execution profile.

RESOURCE_RELIABILITY_SPEC.md §4: every major operation has bounded workers,
queue size, batch size, sequence length, candidate count, retry count,
timeout, and a memory target. No unbounded task spawning, retry loop, or
in-memory accumulation is permitted anywhere downstream that consumes a
``ResourceBudget`` — every field here is a concrete finite value, never
``None``/"unlimited".
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.legal_ai.runtime.cpu_topology import CPUTopology
from src.legal_ai.runtime.profiles import ExecutionProfile


@dataclass(frozen=True)
class ResourceBudget:
    max_workers: int
    max_queue_size: int
    dense_batch_size: int
    rerank_batch_size: int  # 0 means "reranker off by policy" (CPU-minimal, per spec §2)
    max_seq_length: int
    max_candidates: int
    max_retries: int
    request_timeout_seconds: float
    memory_target_bytes: int


# CPU-minimal: small bounded batches, limited workers, reranker off by
# policy, short timeout so a constrained host fails fast instead of
# queuing work it cannot finish (§2, §4).
_CPU_MINIMAL = ResourceBudget(
    max_workers=1,
    max_queue_size=4,
    dense_batch_size=8,
    rerank_batch_size=0,
    max_seq_length=512,
    max_candidates=20,
    max_retries=1,
    request_timeout_seconds=20.0,
    memory_target_bytes=2 * 1024**3,
)

# Balanced: normal workstation/server execution — the default for adequate,
# known hardware.
_BALANCED = ResourceBudget(
    max_workers=4,
    max_queue_size=16,
    dense_batch_size=32,
    rerank_batch_size=16,
    max_seq_length=1024,
    max_candidates=40,
    max_retries=2,
    request_timeout_seconds=30.0,
    memory_target_bytes=8 * 1024**3,
)

# Accelerated: GPU present with sufficient VRAM (per profiles.py). Higher
# throughput settings, but memory_target_bytes here is VRAM-scoped headroom,
# not host RAM — model residency (§5) governs what may be resident at once.
_ACCELERATED = ResourceBudget(
    max_workers=6,
    max_queue_size=32,
    dense_batch_size=64,
    rerank_batch_size=32,
    max_seq_length=1024,
    max_candidates=60,
    max_retries=2,
    request_timeout_seconds=20.0,
    memory_target_bytes=4 * 1024**3,
)

# Remote-LLM: retrieval/evidence local, generation via a remote API — bigger
# timeout and one extra bounded retry to absorb normal network/provider
# latency, but still a concrete finite ceiling, never unlimited (§10).
_REMOTE_LLM = ResourceBudget(
    max_workers=4,
    max_queue_size=16,
    dense_batch_size=16,
    rerank_batch_size=8,
    max_seq_length=1024,
    max_candidates=30,
    max_retries=3,
    request_timeout_seconds=60.0,
    memory_target_bytes=4 * 1024**3,
)

_PROFILE_BUDGETS: dict[ExecutionProfile, ResourceBudget] = {
    ExecutionProfile.CPU_MINIMAL: _CPU_MINIMAL,
    ExecutionProfile.BALANCED: _BALANCED,
    ExecutionProfile.ACCELERATED: _ACCELERATED,
    ExecutionProfile.REMOTE_LLM: _REMOTE_LLM,
}


# Per-profile (min_workers, max_workers) clamp applied when scaling
# max_workers from real effective-core count (see budget_for_profile).
# CPU_MINIMAL is deliberately absent: that profile stays pinned at 1
# worker regardless of core count — it is chosen specifically *because*
# hardware is constrained, and adding workers there would defeat the point.
_WORKER_CLAMP: dict[ExecutionProfile, tuple[int, int]] = {
    ExecutionProfile.BALANCED: (2, 8),
    # CPU-bound preprocessing/queueing feeding a GPU: more CPU workers past
    # a point don't help and compete with the GPU pipeline for host RAM/PCIe.
    ExecutionProfile.ACCELERATED: (2, 6),
    # I/O-bound (waiting on a remote API) — can usefully run more concurrent
    # workers than physical cores, but still capped, never unbounded (§4/§10).
    ExecutionProfile.REMOTE_LLM: (4, 16),
}
_REMOTE_LLM_WORKER_MULTIPLIER = 2  # I/O-bound: workers may exceed effective_cores, within the clamp


def budget_for_profile(
    profile: ExecutionProfile, cpu_topology: CPUTopology | None = None
) -> ResourceBudget:
    """Return the bounded resource budget for *profile*.

    A dict lookup rather than an if/elif ladder: adding a profile becomes a
    data change, and forgetting to register a budget for a new profile fails
    loudly with ``KeyError`` instead of silently defaulting to an unbounded
    or wrong-profile budget.

    When *cpu_topology* is supplied, ``max_workers`` is scaled from
    ``cpu_topology.effective_cores`` — the container/affinity-aware core
    count, not the raw host count — and clamped to a profile-appropriate
    ``[min, max]`` range so a 1-core container never gets an
    over-provisioned worker pool and a 64-core host never gets an
    unbounded one. Without *cpu_topology* (the default), the static
    baseline budget is returned unchanged, so existing callers that don't
    yet pass hardware info keep deterministic, previously-verified values.
    """
    base = _PROFILE_BUDGETS[profile]
    if cpu_topology is None or profile not in _WORKER_CLAMP:
        return base

    low, high = _WORKER_CLAMP[profile]
    if profile is ExecutionProfile.REMOTE_LLM:
        raw = cpu_topology.effective_cores * _REMOTE_LLM_WORKER_MULTIPLIER
    else:
        raw = cpu_topology.effective_cores  # leave headroom for the OS/other processes
        if profile is ExecutionProfile.BALANCED:
            raw = max(1, raw - 1)
    scaled_workers = max(low, min(high, raw))
    return replace(base, max_workers=scaled_workers)


__all__ = ["ResourceBudget", "budget_for_profile"]
