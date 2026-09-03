"""faults.py — fault taxonomy and bounded recovery bookkeeping.

RESOURCE_RELIABILITY_SPEC.md §9-11: a minimum fault taxonomy, an explicit
bounded recovery policy per class, and a normalized ``FailureEvent`` shape
for promoting sanitized failures into regression/evaluation cases. "A
failure must never trigger unlimited retries" (§10) is enforced structurally
here: ``RecoveryPolicy.max_attempts`` is a plain ``int``, so there is no
``None``/"unlimited" value it could ever hold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class FaultClass(StrEnum):
    """Minimum fault taxonomy (RESOURCE_RELIABILITY_SPEC.md §9)."""

    INVALID_INPUT = "invalid_input"
    DATA_CORRUPTION = "data_corruption"
    ARTIFACT_MISSING = "artifact_missing"
    ARTIFACT_INCOMPATIBLE = "artifact_incompatible"
    MODEL_LOAD_FAILURE = "model_load_failure"
    OUT_OF_MEMORY = "out_of_memory"
    TIMEOUT = "timeout"
    BACKEND_FAILURE = "backend_failure"
    RATE_LIMIT = "rate_limit"
    DEPENDENCY_FAILURE = "dependency_failure"
    RETRIEVAL_MISS = "retrieval_miss"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    CITATION_MISMATCH = "citation_mismatch"
    JURISDICTION_CONFLICT = "jurisdiction_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    UNKNOWN = "unknown"


class RecoveryAction(StrEnum):
    """Concrete recovery actions named in RESOURCE_RELIABILITY_SPEC.md §10."""

    REDUCE_BATCH_AND_RETRY = "reduce_batch_and_retry"
    FALLBACK_BACKEND = "fallback_backend"
    BOUNDED_BACKOFF_RETRY = "bounded_backoff_retry"
    QUARANTINE_AND_FAIL_CLOSED = "quarantine_and_fail_closed"
    RETURN_INSUFFICIENT_EVIDENCE = "return_insufficient_evidence"
    REJECT_AND_REPAIR = "reject_and_repair"
    SURFACE_WARNING_SELECT_VERIFIED = "surface_warning_select_verified"
    FAIL_CLOSED_NO_RETRY = "fail_closed_no_retry"


@dataclass(frozen=True)
class RecoveryPolicy:
    action: RecoveryAction
    max_attempts: int  # concrete and finite, always — never "unlimited" (§10)
    backoff_seconds: float = 0.0


# One explicit, bounded policy per class. DEPENDENCY_FAILURE and UNKNOWN
# default to fail-closed/no-retry rather than guessing a recovery path this
# module has no specific knowledge of — a wrong guessed retry is worse than
# an honest, immediate failure.
_DEFAULT_POLICIES: dict[FaultClass, RecoveryPolicy] = {
    FaultClass.INVALID_INPUT: RecoveryPolicy(RecoveryAction.FAIL_CLOSED_NO_RETRY, max_attempts=0),
    FaultClass.DATA_CORRUPTION: RecoveryPolicy(RecoveryAction.QUARANTINE_AND_FAIL_CLOSED, max_attempts=0),
    FaultClass.ARTIFACT_MISSING: RecoveryPolicy(RecoveryAction.QUARANTINE_AND_FAIL_CLOSED, max_attempts=0),
    FaultClass.ARTIFACT_INCOMPATIBLE: RecoveryPolicy(RecoveryAction.QUARANTINE_AND_FAIL_CLOSED, max_attempts=0),
    FaultClass.MODEL_LOAD_FAILURE: RecoveryPolicy(RecoveryAction.FALLBACK_BACKEND, max_attempts=1),
    FaultClass.OUT_OF_MEMORY: RecoveryPolicy(RecoveryAction.REDUCE_BATCH_AND_RETRY, max_attempts=1),
    FaultClass.TIMEOUT: RecoveryPolicy(RecoveryAction.BOUNDED_BACKOFF_RETRY, max_attempts=2, backoff_seconds=1.0),
    FaultClass.BACKEND_FAILURE: RecoveryPolicy(RecoveryAction.FALLBACK_BACKEND, max_attempts=1),
    FaultClass.RATE_LIMIT: RecoveryPolicy(RecoveryAction.BOUNDED_BACKOFF_RETRY, max_attempts=3, backoff_seconds=2.0),
    FaultClass.DEPENDENCY_FAILURE: RecoveryPolicy(RecoveryAction.FAIL_CLOSED_NO_RETRY, max_attempts=0),
    FaultClass.RETRIEVAL_MISS: RecoveryPolicy(RecoveryAction.RETURN_INSUFFICIENT_EVIDENCE, max_attempts=0),
    FaultClass.EVIDENCE_INSUFFICIENT: RecoveryPolicy(RecoveryAction.RETURN_INSUFFICIENT_EVIDENCE, max_attempts=0),
    FaultClass.CITATION_MISMATCH: RecoveryPolicy(RecoveryAction.REJECT_AND_REPAIR, max_attempts=1),
    FaultClass.JURISDICTION_CONFLICT: RecoveryPolicy(RecoveryAction.SURFACE_WARNING_SELECT_VERIFIED, max_attempts=0),
    FaultClass.TEMPORAL_CONFLICT: RecoveryPolicy(RecoveryAction.SURFACE_WARNING_SELECT_VERIFIED, max_attempts=0),
    FaultClass.UNKNOWN: RecoveryPolicy(RecoveryAction.FAIL_CLOSED_NO_RETRY, max_attempts=0),
}


def recovery_policy_for(fault_class: FaultClass) -> RecoveryPolicy:
    """Return the bounded recovery policy registered for *fault_class*.

    Every ``FaultClass`` member is registered in ``_DEFAULT_POLICIES`` —
    enforced by ``test_fault_taxonomy.py`` — so this can never silently fall
    through to an implicit "retry forever" default.
    """
    return _DEFAULT_POLICIES[fault_class]


@dataclass
class FailureEvent:
    """Normalized failure record (RESOURCE_RELIABILITY_SPEC.md §11).

    Deliberately does not accept a raw exception object or an arbitrary
    payload — only ``sanitized_context``, a caller-prepared dict that must
    already exclude document text/PII, is stored. Promoting a
    ``FailureEvent`` into a regression/evaluation case is a separate,
    reviewed step (§11: "must not directly modify production code,
    thresholds, prompts, or model weights"); this dataclass only records.
    """

    failure_id: str
    request_id: str | None
    operation: str
    stage: str
    error_class: FaultClass
    error_signature: str
    recovery_action: RecoveryAction
    recovery_result: str  # "recovered" | "degraded" | "failed"
    software_version: str | None = None
    model_version: str | None = None
    knowledge_release: str | None = None
    dataset_version: str | None = None
    execution_profile: str | None = None
    hardware_summary: str | None = None
    resource_signals: dict[str, float] = field(default_factory=dict)
    sanitized_context: dict[str, str] = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "failure_id": self.failure_id,
            "request_id": self.request_id,
            "operation": self.operation,
            "stage": self.stage,
            "error_class": self.error_class.value,
            "error_signature": self.error_signature,
            "recovery_action": self.recovery_action.value,
            "recovery_result": self.recovery_result,
            "software_version": self.software_version,
            "model_version": self.model_version,
            "knowledge_release": self.knowledge_release,
            "dataset_version": self.dataset_version,
            "execution_profile": self.execution_profile,
            "hardware_summary": self.hardware_summary,
            "resource_signals": dict(self.resource_signals),
            "sanitized_context": dict(self.sanitized_context),
            "occurred_at": self.occurred_at,
        }


__all__ = [
    "FaultClass",
    "RecoveryAction",
    "RecoveryPolicy",
    "recovery_policy_for",
    "FailureEvent",
]
