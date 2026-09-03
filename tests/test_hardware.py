from __future__ import annotations

import subprocess

from src.legal_ai.runtime.hardware import (
    CUDAProbeResult,
    discover_hardware,
    probe_cuda,
)


def test_discover_hardware_never_raises_and_returns_known_python_version():
    snapshot = discover_hardware()
    assert snapshot.python_version
    assert snapshot.os_name
    # CPU count is always available from os.cpu_count() on supported platforms.
    assert snapshot.cpu_count_logical is None or snapshot.cpu_count_logical > 0


def test_discover_hardware_can_skip_cuda_probe():
    snapshot = discover_hardware(probe_cuda_enabled=False)
    assert snapshot.cuda.probe_status == "skipped"
    assert snapshot.cuda.available is False


def test_probe_cuda_degrades_gracefully_when_torch_missing_or_no_gpu():
    """Real-environment probe: whatever this host has (no GPU, no torch, or
    a GPU), the probe must never raise and must always return a
    CUDAProbeResult with an explicit status."""
    result = probe_cuda()
    assert isinstance(result, CUDAProbeResult)
    assert result.probe_status in {"ok", "unavailable", "probe_error", "timeout"}
    if not result.available:
        assert result.device_count == 0
        assert result.devices == ()


def test_probe_cuda_times_out_without_raising(monkeypatch):
    """Simulates a hung child process — the probe must degrade to
    probe_status='timeout' rather than propagating TimeoutExpired."""

    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="python", timeout=0.01)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    result = probe_cuda(timeout_seconds=0.01)
    assert result.available is False
    assert result.probe_status == "timeout"
    assert result.error is not None


def test_probe_cuda_handles_unparseable_output(monkeypatch):
    class _FakeCompleted:
        returncode = 0
        stdout = "not json at all"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted())
    result = probe_cuda()
    assert result.available is False
    assert result.probe_status == "probe_error"


def test_probe_cuda_handles_nonzero_exit_code(monkeypatch):
    class _FakeCompleted:
        returncode = 1
        stdout = ""
        stderr = "Segmentation fault"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted())
    result = probe_cuda()
    assert result.available is False
    assert result.probe_status == "probe_error"
    assert "Segmentation fault" in (result.error or "")


def test_hardware_snapshot_to_dict_is_json_serializable():
    import json

    snapshot = discover_hardware(probe_cuda_enabled=False)
    # Must not raise: nested CUDAProbeResult/GPUDevice dataclasses need to
    # already be plain dicts/lists after to_dict().
    json.dumps(snapshot.to_dict())
