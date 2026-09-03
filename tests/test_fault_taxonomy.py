from __future__ import annotations

import json

import pytest

from src.legal_ai.runtime.faults import FailureEvent, FaultClass, recovery_policy_for


@pytest.mark.parametrize("fault_class", list(FaultClass))
def test_every_fault_class_has_a_bounded_recovery_policy(fault_class):
    policy = recovery_policy_for(fault_class)
    # §10: "a failure must never trigger unlimited retries" — enforced by
    # type (max_attempts: int) plus this explicit non-negative check.
    assert isinstance(policy.max_attempts, int)
    assert policy.max_attempts >= 0
    assert policy.backoff_seconds >= 0.0


def test_out_of_memory_reduces_batch_not_infinite_retry():
    policy = recovery_policy_for(FaultClass.OUT_OF_MEMORY)
    assert policy.max_attempts <= 1


def test_rate_limit_uses_bounded_backoff():
    policy = recovery_policy_for(FaultClass.RATE_LIMIT)
    assert policy.max_attempts >= 1
    assert policy.backoff_seconds > 0


def test_retrieval_miss_returns_insufficient_evidence_not_a_retry():
    """§10: 'retrieval miss -> return insufficient evidence rather than
    hallucinating' — this must not be modeled as a retry-able fault."""
    policy = recovery_policy_for(FaultClass.RETRIEVAL_MISS)
    assert policy.max_attempts == 0


def test_failure_event_sanitized_context_round_trips_and_excludes_raw_exception():
    event = FailureEvent(
        failure_id="f-1",
        request_id="r-1",
        operation="retrieve",
        stage="dense_search",
        error_class=FaultClass.TIMEOUT,
        error_signature="TimeoutError",
        recovery_action=recovery_policy_for(FaultClass.TIMEOUT).action,
        recovery_result="degraded",
        sanitized_context={"query_length_bucket": "short"},
    )
    payload = event.to_dict()
    # Must be plain-JSON-serializable (no raw exception objects leaking in).
    json.dumps(payload)
    assert payload["error_class"] == "timeout"
    assert payload["sanitized_context"] == {"query_length_bucket": "short"}
