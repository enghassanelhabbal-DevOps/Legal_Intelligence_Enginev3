"""budgets.py — bounded resource budgets per execution profile.

RESOURCE_RELIABILITY_SPEC.md §4: every major operation has bounded workers,
queue size, batch size, sequence length, candidate count, retry count,
timeout, and a memory target. No unbounded task spawning, retry loop, or
in-memory accumulation is permitted anywhere downstream that consumes a
``ResourceBudget`` — every field here is a concrete finite value, never
``None``/"unlimited".
"""

from __future__ import annotations

from dataclasses import dataclass

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


def budget_for_profile(profile: ExecutionProfile) -> ResourceBudget:
    """Return the bounded resource budget for *profile*.

    A dict lookup rather than an if/elif ladder: adding a profile becomes a
    data change, and forgetting to register a budget for a new profile fails
    loudly with ``KeyError`` instead of silently defaulting to an unbounded
    or wrong-profile budget.
    """
    return _PROFILE_BUDGETS[profile]


__all__ = ["ResourceBudget", "budget_for_profile"]
