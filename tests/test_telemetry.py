from __future__ import annotations

import json
import time

from src.legal_ai.runtime.telemetry import resource_signals, start_trace


def test_start_trace_generates_request_id_when_absent():
    trace = start_trace("retrieve")
    assert trace.request_id
    assert trace.operation == "retrieve"
    assert trace.outcome == "in_progress"


def test_stage_context_manager_records_timing_even_on_exception():
    trace = start_trace("retrieve", request_id="r-1")
    try:
        with trace.stage("dense_search"):
            time.sleep(0.001)
            raise ValueError("boom")
    except ValueError:
        pass
    assert len(trace.stage_timings) == 1
    assert trace.stage_timings[0].stage == "dense_search"
    assert trace.stage_timings[0].duration_seconds >= 0


def test_total_duration_sums_all_stages():
    trace = start_trace("retrieve", request_id="r-1")
    with trace.stage("a"):
        time.sleep(0.001)
    with trace.stage("b"):
        time.sleep(0.001)
    assert trace.total_duration_seconds() >= trace.stage_timings[0].duration_seconds


def test_trace_to_dict_is_json_serializable_and_excludes_payload_text():
    trace = start_trace("retrieve", request_id="r-1", execution_profile="balanced")
    with trace.stage("dense_search"):
        pass
    trace.add_warning("low candidate count")
    trace.finish("degraded")
    payload = trace.to_dict()
    json.dumps(payload)  # must not raise
    assert payload["outcome"] == "degraded"
    assert payload["warnings"] == ["low candidate count"]
    # Contract: only stage NAMES are recorded, never arbitrary payload text.
    assert set(payload.keys()) == {
        "request_id", "operation", "execution_profile", "model_backend",
        "knowledge_release", "stage_timings", "total_duration_seconds",
        "warnings", "recovery_action", "outcome",
    }


def test_resource_signals_never_raises():
    signals = resource_signals()
    assert isinstance(signals, dict)


def test_resource_signals_degrades_when_process_disappears(monkeypatch):
    import psutil

    def raise_no_such_process():
        raise psutil.NoSuchProcess(12345)

    monkeypatch.setattr(psutil, "Process", raise_no_such_process)

    assert resource_signals() == {}
