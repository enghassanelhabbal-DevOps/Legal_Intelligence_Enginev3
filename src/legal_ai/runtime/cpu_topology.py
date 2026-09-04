"""cpu_topology.py — container-aware, affinity-aware CPU topology discovery.

Why this exists (production ML/AI practice, not theory): ``os.cpu_count()``
alone is one of the most common sources of silent misconfiguration in
containerized inference deployments. It reports the **host's** core count,
not what the current process is actually allowed to use. On Docker,
Kubernetes, and most managed hosting (including Streamlit Community Cloud),
a container is routinely capped via a cgroup CPU quota — e.g. "2.0 cores" —
while sitting on a 16/32/64-core host. If NumPy/PyTorch/MKL each spin up a
thread pool sized to the host's ``os.cpu_count()`` inside that container,
every worker process oversubscribes the same 2 physical cores, causing
context-switch thrashing and unpredictable p95 latency under load — a
well-documented, extremely common real-world failure mode.

This module discovers CPU capacity the way a scheduler actually enforces
it: the intersection of (a) any cgroup CPU quota, (b) the process's CPU
affinity mask (respects ``taskset``/``cpuset``/SLURM allocations), and (c)
the host's logical core count — and reports the most-constrained,
i.e. *actually usable*, value as ``effective_cores``. This is the same
resolution strategy used by mainstream container-aware runtimes (e.g. the
JVM's ``-XX:ActiveProcessorCount`` auto-detection, Node's
``UV_THREADPOOL_SIZE`` guidance, and Ray's/HuggingFace's own
cgroup-aware worker-count detection).

Every probe here follows the same rule as ``runtime.hardware``: degrade to
an explicit "unknown"/``None`` value, never raise.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ContainerRuntime(StrEnum):
    NONE = "none"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    UNKNOWN_CONTAINER = "unknown_container"


@dataclass(frozen=True)
class CPUTopology:
    logical_cores_host: int | None
    physical_cores_host: int | None
    affinity_cores: int | None  # None on platforms without sched_getaffinity (Windows/macOS)
    cgroup_quota_cores: float | None  # fractional — e.g. 2.5 means 2.5 CPU-cores worth of quota
    container_runtime: ContainerRuntime
    hyperthreading_likely: bool | None
    effective_cores: int  # the number every worker/thread-pool sizing decision should use
    # which signal was binding: cgroup_quota | affinity_mask | host_logical | unknown_default
    effective_cores_source: str

    def to_dict(self) -> dict:
        return {
            "logical_cores_host": self.logical_cores_host,
            "physical_cores_host": self.physical_cores_host,
            "affinity_cores": self.affinity_cores,
            "cgroup_quota_cores": self.cgroup_quota_cores,
            "container_runtime": self.container_runtime.value,
            "hyperthreading_likely": self.hyperthreading_likely,
            "effective_cores": self.effective_cores,
            "effective_cores_source": self.effective_cores_source,
        }


def _logical_cores_host() -> int | None:
    return os.cpu_count()


def _physical_cores_host() -> int | None:
    try:
        import psutil

        return psutil.cpu_count(logical=False)
    except ImportError:
        return None


def _affinity_cores() -> int | None:
    """CPU affinity mask size. Linux-only (``os.sched_getaffinity`` does not
    exist on Windows/macOS) — respects ``taskset``, ``cpuset``, and SLURM/
    batch-scheduler core pinning, which ``os.cpu_count()`` ignores entirely.
    """
    getter = getattr(os, "sched_getaffinity", None)
    if getter is None:
        return None
    try:
        return len(getter(0))
    except OSError:
        return None


def _detect_container_runtime() -> ContainerRuntime:
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return ContainerRuntime.KUBERNETES
    if Path("/.dockerenv").exists():
        return ContainerRuntime.DOCKER
    try:
        cgroup_text = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore")
        if "kubepods" in cgroup_text:
            return ContainerRuntime.KUBERNETES
        if "docker" in cgroup_text or "containerd" in cgroup_text:
            return ContainerRuntime.DOCKER
    except OSError:
        pass
    return ContainerRuntime.NONE


def _cgroup_quota_cores() -> float | None:
    """Effective CPU quota from cgroup v2 (``cpu.max``) or cgroup v1
    (``cpu.cfs_quota_us`` / ``cpu.cfs_period_us``) — the number of cores a
    container is actually *allowed* to use. Returns ``None`` (no quota
    set / not in a cgroup-limited environment / unreadable), never raises.
    """
    v2_path = Path("/sys/fs/cgroup/cpu.max")
    try:
        if v2_path.exists():
            quota_str, period_str = v2_path.read_text(encoding="utf-8").strip().split()
            if quota_str != "max":
                quota, period = int(quota_str), int(period_str)
                if period > 0:
                    return quota / period
    except (OSError, ValueError):
        pass

    try:
        quota_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        period_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        if quota_path.exists() and period_path.exists():
            quota = int(quota_path.read_text(encoding="utf-8").strip())
            period = int(period_path.read_text(encoding="utf-8").strip())
            if quota > 0 and period > 0:
                return quota / period
    except (OSError, ValueError):
        pass

    return None


def discover_cpu_topology() -> CPUTopology:
    """Best-effort, never-raises CPU topology discovery.

    ``effective_cores`` resolution takes the *minimum* of every available
    signal — each constraint is independently binding, so a cgroup quota of
    2 cores on a 64-core host still means 2 usable cores regardless of what
    affinity or host core count report. Precedence when signals disagree
    (most to least authoritative): cgroup quota > CPU affinity mask > host
    logical core count. Floors fractional quotas down (2.5 -> 2) and floors
    the final result at 1 — a worker/thread pool sized to 0 is a bug, not a
    valid "constrained" state.
    """
    logical_host = _logical_cores_host()
    physical_host = _physical_cores_host()
    affinity = _affinity_cores()
    cgroup_quota = _cgroup_quota_cores()
    container_runtime = _detect_container_runtime()

    candidates: list[tuple[str, float]] = []
    if cgroup_quota is not None:
        candidates.append(("cgroup_quota", cgroup_quota))
    if affinity is not None:
        candidates.append(("affinity_mask", float(affinity)))
    if logical_host is not None:
        candidates.append(("host_logical", float(logical_host)))

    if candidates:
        source, value = min(candidates, key=lambda c: c[1])
        effective = max(1, int(value))
    else:
        source, effective = "unknown_default", 1

    hyperthreading_likely = (
        logical_host is not None and physical_host is not None and logical_host > physical_host
    )

    return CPUTopology(
        logical_cores_host=logical_host,
        physical_cores_host=physical_host,
        affinity_cores=affinity,
        cgroup_quota_cores=cgroup_quota,
        container_runtime=container_runtime,
        hyperthreading_likely=hyperthreading_likely,
        effective_cores=effective,
        effective_cores_source=source,
    )


def recommended_thread_env(topology: CPUTopology) -> dict[str, str]:
    """Environment-variable overrides that prevent BLAS/OMP thread
    oversubscription — standard practice for CPU-inference ML deployments.
    Without this, NumPy/MKL/OpenBLAS each independently default to using
    ALL host cores; running several worker processes in parallel (each
    spawning its own internal thread pool) causes N-times core
    oversubscription and degraded, unpredictable latency under load.

    Only includes variables that are genuinely read automatically by their
    respective libraries at import time (OMP/MKL/OpenBLAS/NumExpr, plus
    HuggingFace tokenizers' fork-safety flag). Deliberately does NOT
    include a fabricated ``TORCH_NUM_THREADS`` — PyTorch has no such
    environment variable; callers must call
    ``torch.set_num_threads(topology.effective_cores)`` explicitly in code,
    before running any CPU inference.

    Returned as a plain dict for the caller to apply (e.g. at process
    bootstrap, before importing numpy/torch) — this module never mutates
    ``os.environ`` itself; environment mutation is a caller-owned side
    effect, not a discovery-layer concern.
    """
    n = str(topology.effective_cores)
    return {
        "OMP_NUM_THREADS": n,
        "MKL_NUM_THREADS": n,
        "OPENBLAS_NUM_THREADS": n,
        "NUMEXPR_NUM_THREADS": n,
        "TOKENIZERS_PARALLELISM": "false",
    }


__all__ = [
    "ContainerRuntime",
    "CPUTopology",
    "discover_cpu_topology",
    "recommended_thread_env",
]
