from __future__ import annotations

from src.legal_ai.runtime.hardware import CUDAProbeResult, GPUDevice, HardwareSnapshot
from src.legal_ai.runtime.profiles import (
    DEFAULT_LOW_RAM_THRESHOLD_BYTES,
    MIN_ACCELERATED_VRAM_BYTES,
    ExecutionProfile,
    resolve_profile,
)


def _snapshot(*, ram_bytes: int | None, cuda: CUDAProbeResult) -> HardwareSnapshot:
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
    )


def test_override_always_wins():
    snap = _snapshot(ram_bytes=64 * 1024**3, cuda=CUDAProbeResult(available=True, device_count=1,
                      devices=(GPUDevice(0, "RTX 4090", 24 * 1024**3, "8.9"),)))
    assert resolve_profile(snap, override=ExecutionProfile.CPU_MINIMAL) == ExecutionProfile.CPU_MINIMAL


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
