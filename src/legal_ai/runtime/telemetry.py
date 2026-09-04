"""telemetry.py — lightweight per-operation observability.

RESOURCE_RELIABILITY_SPEC.md §12: instrumentation must stay lightweight;
high-cardinality or sensitive payload logging is prohibited by default.
``OperationTrace`` therefore records only stage *names* and durations, plus
small policy/outcome metadata — never query text, document text, or other
unbounded/sensitive payloads.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StageTiming:
    stage: str
    duration_seconds: float


@dataclass
class OperationTrace:
    """Per-request trace: stage timings + resource/outcome metadata only.

    Construct with :func:`start_trace`. Use :meth:`stage` as a context
    manager to time each pipeline stage.
    """

    request_id: str
    operation: str
    execution_profile: str | None = None
    model_backend: str | None = None
    knowledge_release: str | None = None
    stage_timings: list[StageTiming] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recovery_action: str | None = None
    outcome: str = "in_progress"  # "success" | "degraded" | "failed" | "in_progress"

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.stage_timings.append(
                StageTiming(stage=name, duration_seconds=time.perf_counter() - start)
            )

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def finish(self, outcome: str) -> None:
        self.outcome = outcome

    def total_duration_seconds(self) -> float:
        return sum(t.duration_seconds for t in self.stage_timings)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "execution_profile": self.execution_profile,
            "model_backend": self.model_backend,
            "knowledge_release": self.knowledge_release,
            "stage_timings": [
                {"stage": t.stage, "duration_seconds": t.duration_seconds}
                for t in self.stage_timings
            ],
            "total_duration_seconds": self.total_duration_seconds(),
            "warnings": self.warnings,
            "recovery_action": self.recovery_action,
            "outcome": self.outcome,
        }


def start_trace(
    operation: str,
    *,
    request_id: str | None = None,
    execution_profile: str | None = None,
) -> OperationTrace:
    """Start a new trace. Generates a request_id if the caller has none yet."""
    return OperationTrace(
        request_id=request_id or uuid.uuid4().hex,
        operation=operation,
        execution_profile=execution_profile,
    )


def resource_signals() -> dict[str, float]:
    """Best-effort lightweight process resource snapshot (RSS, CPU%).

    Returns ``{}`` if psutil is unavailable — never raises, matching the
    degrade-not-fail rule used throughout ``runtime.hardware`` (§3/§12).
    """
    try:
        import psutil  # type: ignore

        proc = psutil.Process()
        with proc.oneshot():
            rss_bytes = float(proc.memory_info().rss)
            cpu_percent = float(proc.cpu_percent(interval=None))
        return {"rss_bytes": rss_bytes, "cpu_percent": cpu_percent}
    except ImportError:
        return {}


__all__ = ["StageTiming", "OperationTrace", "start_trace", "resource_signals"]
