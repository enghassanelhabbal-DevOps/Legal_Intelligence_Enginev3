"""runtime — Stage 2 canonical runtime/resource governance foundation.

Per docs/DELIVERY_STAGE_PLAN.md Stage 2 and docs/RESOURCE_RELIABILITY_SPEC.md:
hardware discovery, execution-profile resolution, bounded resource budgets, a
minimum fault taxonomy with bounded recovery policies, and lightweight
per-operation telemetry.

Nothing in this package makes a network call, loads a model, or touches the
retrieval/generation pipeline directly — it is pure discovery/policy,
consumed by the pipeline layers that actually do the work. This keeps it
unit-testable without torch, GPUs, or a live corpus.
"""

from src.legal_ai.runtime.budgets import ResourceBudget, budget_for_profile
from src.legal_ai.runtime.faults import (
    FailureEvent,
    FaultClass,
    RecoveryAction,
    RecoveryPolicy,
    recovery_policy_for,
)
from src.legal_ai.runtime.hardware import (
    CUDAProbeResult,
    GPUDevice,
    HardwareSnapshot,
    discover_hardware,
    probe_cuda,
)
from src.legal_ai.runtime.profiles import ExecutionProfile, resolve_profile
from src.legal_ai.runtime.telemetry import OperationTrace, StageTiming, resource_signals, start_trace

__all__ = [
    "ResourceBudget",
    "budget_for_profile",
    "FailureEvent",
    "FaultClass",
    "RecoveryAction",
    "RecoveryPolicy",
    "recovery_policy_for",
    "CUDAProbeResult",
    "GPUDevice",
    "HardwareSnapshot",
    "discover_hardware",
    "probe_cuda",
    "ExecutionProfile",
    "resolve_profile",
    "OperationTrace",
    "StageTiming",
    "resource_signals",
    "start_trace",
]
