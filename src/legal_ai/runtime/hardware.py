"""hardware.py — best-effort hardware discovery for execution-profile resolution.

Per docs/RESOURCE_RELIABILITY_SPEC.md §3: discovery must not fail the
application merely because an optional hardware probe is unavailable. Every
probe in this module degrades to an explicit "unavailable"/"unknown" status
rather than raising or hanging the caller.

CUDA discovery is deliberately NOT an in-process ``torch.cuda.is_available()``
call. DR-028: an in-process probe carries a confirmed deadlock risk once a
CUDA context has already been initialized in a process that is later forked
(pytest-xdist workers, Streamlit's re-run/thread model, and the
multiprocessing "fork" start method are all affected paths in this project) —
CUDA is not fork-safe, and the forked child can hang inside the driver
indefinitely instead of raising an exception that could be caught. A bounded,
*spawned* subprocess sidesteps this entirely: it never inherits the parent's
CUDA context, and a hard timeout guarantees discovery cannot hang the caller
even if the driver itself misbehaves.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field

from src.legal_ai.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_CUDA_PROBE_TIMEOUT_SECONDS = 15.0

# Kept as a standalone script string (not "python -c" string concatenation
# built from f-strings) so it is trivially auditable and has no dependency
# on shell quoting of the caller's environment.
_CUDA_PROBE_SCRIPT = r"""
import json
result = {"available": False, "device_count": 0, "devices": [], "error": None}
try:
    import torch
    result["available"] = bool(torch.cuda.is_available())
    if result["available"]:
        result["device_count"] = torch.cuda.device_count()
        for i in range(result["device_count"]):
            props = torch.cuda.get_device_properties(i)
            result["devices"].append({
                "index": i,
                "name": props.name,
                "total_memory_bytes": int(props.total_memory),
                "compute_capability": f"{props.major}.{props.minor}",
            })
except Exception as exc:  # noqa: BLE001 - probe must never propagate a raw traceback
    result["error"] = f"{type(exc).__name__}: {exc}"
print(json.dumps(result))
"""


@dataclass(frozen=True)
class GPUDevice:
    index: int
    name: str
    total_memory_bytes: int
    compute_capability: str


@dataclass(frozen=True)
class CUDAProbeResult:
    available: bool
    device_count: int
    devices: tuple[GPUDevice, ...] = ()
    probe_status: str = "ok"  # "ok" | "unavailable" | "timeout" | "probe_error" | "skipped"
    error: str | None = None


def probe_cuda(timeout_seconds: float = _DEFAULT_CUDA_PROBE_TIMEOUT_SECONDS) -> CUDAProbeResult:
    """Discover CUDA/GPU availability in an isolated, spawned child process.

    Never raises. Any failure mode (missing torch, driver error, timeout,
    unparseable output) degrades to ``available=False`` with a specific
    ``probe_status`` so callers/logs can distinguish "no GPU" from
    "probe itself failed" without treating either as fatal.
    """
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _CUDA_PROBE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("CUDA probe timed out after %.1fs; treating GPU as unavailable", timeout_seconds)
        return CUDAProbeResult(
            available=False, device_count=0, probe_status="timeout",
            error=f"probe exceeded {timeout_seconds}s timeout",
        )
    except OSError as exc:
        logger.warning("CUDA probe subprocess could not be started: %s", exc)
        return CUDAProbeResult(available=False, device_count=0, probe_status="probe_error", error=str(exc))

    if completed.returncode != 0:
        stderr_tail = completed.stderr.strip()[-500:]
        logger.warning("CUDA probe subprocess exited %s: %s", completed.returncode, stderr_tail)
        return CUDAProbeResult(
            available=False, device_count=0, probe_status="probe_error",
            error=stderr_tail or f"exit code {completed.returncode}",
        )

    try:
        lines = [ln for ln in completed.stdout.strip().splitlines() if ln.strip()]
        payload = json.loads(lines[-1]) if lines else {}
    except (json.JSONDecodeError, IndexError) as exc:
        logger.warning("CUDA probe returned unparseable output: %s", exc)
        return CUDAProbeResult(available=False, device_count=0, probe_status="probe_error", error=str(exc))

    if payload.get("error"):
        # torch missing / driver error inside the child — a known, expected
        # outcome on CPU-only hosts, not a discovery-layer bug.
        return CUDAProbeResult(
            available=False, device_count=0, probe_status="probe_error", error=str(payload["error"]),
        )

    devices = tuple(GPUDevice(**d) for d in payload.get("devices", []))
    available = bool(payload.get("available", False))
    return CUDAProbeResult(
        available=available,
        device_count=int(payload.get("device_count", 0)),
        devices=devices,
        probe_status="ok" if available else "unavailable",
    )


@dataclass(frozen=True)
class HardwareSnapshot:
    os_name: str
    os_version: str
    python_version: str
    cpu_count_logical: int | None
    cpu_count_physical: int | None
    total_ram_bytes: int | None
    ram_probe_status: str  # "ok" | "unavailable"
    storage_free_bytes: int | None
    cuda: CUDAProbeResult = field(default_factory=lambda: CUDAProbeResult(available=False, device_count=0))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cuda"]["devices"] = [asdict(dev) for dev in self.cuda.devices]
        return d


def _cpu_counts() -> tuple[int | None, int | None]:
    import os as _os

    logical = _os.cpu_count()
    physical: int | None = None
    try:
        import psutil  # type: ignore

        physical = psutil.cpu_count(logical=False)
    except ImportError:
        physical = None
    return logical, physical


def _total_ram_bytes() -> tuple[int | None, str]:
    try:
        import psutil  # type: ignore

        return int(psutil.virtual_memory().total), "ok"
    except ImportError:
        pass
    # Best-effort fallback so a psutil-less environment still gets a real
    # number on Linux/WSL2 rather than reporting "unavailable" needlessly.
    if platform.system() == "Linux":
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024, "ok"
        except (OSError, ValueError):
            pass
    return None, "unavailable"


def _storage_free_bytes(path: str = ".") -> int | None:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def discover_hardware(
    *,
    probe_cuda_enabled: bool = True,
    cuda_timeout_seconds: float = _DEFAULT_CUDA_PROBE_TIMEOUT_SECONDS,
) -> HardwareSnapshot:
    """Best-effort hardware discovery. Never raises (RESOURCE_RELIABILITY_SPEC.md §3)."""
    logical, physical = _cpu_counts()
    ram_bytes, ram_status = _total_ram_bytes()
    cuda = (
        probe_cuda(timeout_seconds=cuda_timeout_seconds)
        if probe_cuda_enabled
        else CUDAProbeResult(available=False, device_count=0, probe_status="skipped")
    )
    return HardwareSnapshot(
        os_name=platform.system(),
        os_version=platform.version(),
        python_version=platform.python_version(),
        cpu_count_logical=logical,
        cpu_count_physical=physical,
        total_ram_bytes=ram_bytes,
        ram_probe_status=ram_status,
        storage_free_bytes=_storage_free_bytes(),
        cuda=cuda,
    )


__all__ = [
    "GPUDevice",
    "CUDAProbeResult",
    "HardwareSnapshot",
    "probe_cuda",
    "discover_hardware",
]
