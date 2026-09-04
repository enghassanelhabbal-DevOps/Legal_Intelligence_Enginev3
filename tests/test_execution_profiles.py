from __future__ import annotations

from src.legal_ai.runtime.cpu_topology import ContainerRuntime, CPUTopology
from src.legal_ai.runtime.hardware import CUDAProbeResult, GPUDevice, HardwareSnapshot
from src.legal_ai.runtime.profiles import (
    DEFAULT_LOW_CORE_THRESHOLD,
    DEFAULT_LOW_RAM_THRESHOLD_BYTES,
    MIN_ACCELERATED_VRAM_BYTES,
    ExecutionProfile,
    resolve_profile,
)

_AMPLE_CORES = CPUTopology(
    logical_cores_host=8,
    physical_cores_host=4,
    affinity_cores=8,
    cgroup_quota_cores=None,
    container_runtime=ContainerRuntime.NONE,
    hyperthreading_likely=True,
    effective_cores=8,
    effective_cores_source="host_logical",
)


def _snapshot(
    *, ram_bytes: int | None, cuda: CUDAProbeResult, cpu_topology: CPUTopology = _AMPLE_CORES
) -> HardwareSnapshot:
    # cpu_topology defaults to an "ample cores" fixture rather than
    # HardwareSnapshot's own auto-discovery default: real CI/sandbox hosts
    # are frequently affinity-limited to 1 core (exactly the case this
    # module exists to detect — see DR-029), which would make hardware-
    # agnostic tests below flaky depending on what host they happen to run on.
    return HardwareSnapshot(
        os_name="Linux",
        os_version="test",
        python_version="3.12.0",
        cpu_count_logical=8,
        cpu_count_physical=4,
        total_ram_bytes=ram_bytes,
        ram_probe_status="ok" if ram_bytes is not None else "unavailable",
        storage_free_bytes=100 * 1024**3,
        cuda=cuda,
        cpu_topology=cpu_topology,
    )


def test_override_always_wins():
    snap = _snapshot(ram_bytes=64 * 1024**3, cuda=CUDAProbeResult(available=True, device_count=1,
                      devices=(GPUDevice(0, "RTX 4090", 24 * 1024**3, "8.9"),)))
    resolved = resolve_profile(snap, override=ExecutionProfile.CPU_MINIMAL)
    assert resolved == ExecutionProfile.CPU_MINIMAL


def test_sufficient_gpu_selects_accelerated():
    snap = _snapshot(
        ram_bytes=16 * 1024**3,
        cuda=CUDAProbeResult(
            available=True, device_count=1,
            devices=(GPUDevice(0, "M2200", MIN_ACCELERATED_VRAM_BYTES + 1, "5.2"),),
        ),
    )
    assert resolve_profile(snap) == ExecutionProfile.ACCELERATED


def test_gpu_present_but_too_small_does_not_trigger_accelerated():
    """A GPU technically reports CUDA-available but with less VRAM than the
    floor — must not be treated as accelerated (would OOM downstream)."""
    snap = _snapshot(
        ram_bytes=16 * 1024**3,
        cuda=CUDAProbeResult(
            available=True, device_count=1,
            devices=(GPUDevice(0, "tiny GPU", 512 * 1024**2, "3.5"),),
        ),
    )
    assert resolve_profile(snap) == ExecutionProfile.BALANCED


def test_low_ram_no_remote_selects_cpu_minimal():
    snap = _snapshot(ram_bytes=DEFAULT_LOW_RAM_THRESHOLD_BYTES - 1, cuda=CUDAProbeResult(False, 0))
    assert resolve_profile(snap) == ExecutionProfile.CPU_MINIMAL


def test_low_ram_with_remote_configured_selects_remote_llm():
    snap = _snapshot(ram_bytes=DEFAULT_LOW_RAM_THRESHOLD_BYTES - 1, cuda=CUDAProbeResult(False, 0))
    assert resolve_profile(snap, remote_generation_configured=True) == ExecutionProfile.REMOTE_LLM


def test_unknown_ram_fails_toward_cpu_minimal_not_balanced():
    """RAM probe failed entirely — must fail toward the conservative
    profile, not silently assume adequate hardware."""
    snap = _snapshot(ram_bytes=None, cuda=CUDAProbeResult(False, 0))
    assert resolve_profile(snap) == ExecutionProfile.CPU_MINIMAL


def test_unknown_ram_with_remote_configured_selects_remote_llm():
    snap = _snapshot(ram_bytes=None, cuda=CUDAProbeResult(False, 0))
    assert resolve_profile(snap, remote_generation_configured=True) == ExecutionProfile.REMOTE_LLM


def test_adequate_known_ram_selects_balanced():
    snap = _snapshot(ram_bytes=32 * 1024**3, cuda=CUDAProbeResult(False, 0))
    assert resolve_profile(snap) == ExecutionProfile.BALANCED


def test_constrained_container_cores_force_cpu_minimal_despite_ample_ram():
    """A 1-2 vCPU container (Docker/Kubernetes/Streamlit Cloud-style quota)
    with plenty of RAM must still resolve to CPU_MINIMAL — CPU contention,
    not memory, is the binding constraint here (DR-029)."""
    constrained = CPUTopology(
        logical_cores_host=32, physical_cores_host=16, affinity_cores=None,
        cgroup_quota_cores=1.0, container_runtime=ContainerRuntime.KUBERNETES,
        hyperthreading_likely=True, effective_cores=1, effective_cores_source="cgroup_quota",
    )
    snap = _snapshot(
        ram_bytes=64 * 1024**3, cuda=CUDAProbeResult(False, 0), cpu_topology=constrained
    )
    assert resolve_profile(snap) == ExecutionProfile.CPU_MINIMAL


def test_constrained_container_cores_with_remote_configured_selects_remote_llm():
    constrained = CPUTopology(
        logical_cores_host=32, physical_cores_host=16, affinity_cores=None,
        cgroup_quota_cores=1.0, container_runtime=ContainerRuntime.DOCKER,
        hyperthreading_likely=True, effective_cores=1, effective_cores_source="cgroup_quota",
    )
    snap = _snapshot(
        ram_bytes=64 * 1024**3, cuda=CUDAProbeResult(False, 0), cpu_topology=constrained
    )
    resolved = resolve_profile(snap, remote_generation_configured=True)
    assert resolved == ExecutionProfile.REMOTE_LLM


def test_low_core_threshold_is_configurable():
    four_cores = CPUTopology(
        logical_cores_host=4, physical_cores_host=4, affinity_cores=4,
        cgroup_quota_cores=None, container_runtime=ContainerRuntime.NONE,
        hyperthreading_likely=False, effective_cores=4, effective_cores_source="host_logical",
    )
    snap = _snapshot(
        ram_bytes=32 * 1024**3, cuda=CUDAProbeResult(False, 0), cpu_topology=four_cores
    )
    # 4 cores > default threshold (2) -> balanced; caller can raise the bar explicitly
    assert resolve_profile(snap) == ExecutionProfile.BALANCED
    assert resolve_profile(snap, low_core_threshold=4) == ExecutionProfile.CPU_MINIMAL


def test_default_low_core_threshold_value_is_two():
    assert DEFAULT_LOW_CORE_THRESHOLD == 2
