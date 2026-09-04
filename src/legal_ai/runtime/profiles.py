"""profiles.py — execution profile resolution.

Per RESOURCE_RELIABILITY_SPEC.md §2: profiles are policy presets resolved
FROM discovered hardware, not hard-coded device assumptions.
``resolve_profile`` is a pure function over a ``HardwareSnapshot`` (+
optional operator override / remote-generation flag), so it stays fully
unit-testable without touching real hardware or importing torch.
"""

from __future__ import annotations

from enum import StrEnum

from src.legal_ai.runtime.hardware import HardwareSnapshot

# A GPU is reported as CUDA-available by drivers on cards far too small to
# usefully hold a retriever/reranker/generator. 3 GiB is a conservative
# floor below the 4 GiB M2200 dev-hardware target (ARCHITECTURE_CONTRACT.md)
# so a technically-present-but-too-small GPU does not falsely trigger
# ACCELERATED and then OOM downstream.
MIN_ACCELERATED_VRAM_BYTES = 3 * 1024**3

# Below this, prefer CPU-minimal (or remote-LLM if configured) over BALANCED.
DEFAULT_LOW_RAM_THRESHOLD_BYTES = 8 * 1024**3

# Below this many *effective* (container/affinity-aware) cores, force
# CPU-minimal regardless of RAM — a 1-2 vCPU container (common on shared/
# managed hosting, e.g. Streamlit Community Cloud's default tier) cannot
# usefully run a multi-worker "balanced" pipeline even with plenty of RAM;
# CPU contention, not memory, is the binding constraint there.
DEFAULT_LOW_CORE_THRESHOLD = 2


class ExecutionProfile(StrEnum):
    CPU_MINIMAL = "cpu_minimal"
    BALANCED = "balanced"
    ACCELERATED = "accelerated"
    REMOTE_LLM = "remote_llm"


def resolve_profile(
    snapshot: HardwareSnapshot,
    *,
    override: ExecutionProfile | None = None,
    remote_generation_configured: bool = False,
    low_ram_threshold_bytes: int = DEFAULT_LOW_RAM_THRESHOLD_BYTES,
    low_core_threshold: int = DEFAULT_LOW_CORE_THRESHOLD,
) -> ExecutionProfile:
    """Resolve the execution profile for this run.

    Precedence:
      1. explicit operator override — always wins, no discovery needed;
      2. ACCELERATED — a GPU is present with at least ``MIN_ACCELERATED_VRAM_BYTES``;
      3. REMOTE_LLM — a remote generation backend is configured AND local
         hardware is constrained (low/unknown RAM, or few *effective*
         cores — i.e. the container/affinity-aware count from
         ``cpu_topology``, not the raw host core count);
      4. CPU_MINIMAL — RAM is low/unknown, or effective cores are at or
         below ``low_core_threshold`` (fail toward the conservative
         profile on constrained or unreadable hardware);
      5. BALANCED — the default for adequate, known hardware.

    Effective-core awareness matters in practice: a container capped at 1-2
    vCPUs (common on shared/managed hosting) cannot usefully run a
    multi-worker BALANCED pipeline regardless of how much RAM the host
    reports, since ``os.cpu_count()`` alone would see the host's full core
    count and miss the container's actual CPU quota entirely.
    """
    if override is not None:
        return override

    has_gpu = snapshot.cuda.available and snapshot.cuda.device_count > 0
    has_sufficient_vram = has_gpu and any(
        d.total_memory_bytes >= MIN_ACCELERATED_VRAM_BYTES for d in snapshot.cuda.devices
    )
    if has_sufficient_vram:
        return ExecutionProfile.ACCELERATED

    ram_known = snapshot.total_ram_bytes is not None
    ram_is_low = ram_known and snapshot.total_ram_bytes < low_ram_threshold_bytes  # type: ignore[operator]
    cores_are_low = snapshot.cpu_topology.effective_cores <= low_core_threshold
    is_constrained = ram_is_low or not ram_known or cores_are_low

    if remote_generation_configured and is_constrained:
        return ExecutionProfile.REMOTE_LLM

    if is_constrained:
        return ExecutionProfile.CPU_MINIMAL

    return ExecutionProfile.BALANCED


__all__ = [
    "ExecutionProfile",
    "resolve_profile",
    "MIN_ACCELERATED_VRAM_BYTES",
    "DEFAULT_LOW_RAM_THRESHOLD_BYTES",
    "DEFAULT_LOW_CORE_THRESHOLD",
]
