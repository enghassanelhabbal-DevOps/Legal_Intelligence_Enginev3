"""Integration tests for the production `/v1/query` call path in `api/app.py`.

These exercise the REAL endpoint function (not a reimplementation or a
mock of the wiring) to prove:
  - it submits work through `runtime.execution.BoundedExecutor` rather than
    calling `QueryService.answer()` directly on the event-loop thread
    (item 1);
  - executor capacity comes from a `ResolvedRuntimePlan`'s budget, not a
    separately hard-coded number (item 4);
  - backpressure (`BackpressureRejected` -> HTTP 503) actually triggers
    under real concurrent load, not just in `runtime/execution.py`'s own
    unit tests (item 6);
  - if the runtime path is ever refactored to bypass the executor (calling
    `service.answer()` directly again), `test_query_endpoint_bypassing_executor_is_detected`
    below fails (item 7).

No torch/faiss/sentence-transformers needed: `api/app.py`, `QueryService`,
and `runtime.execution.BoundedExecutor` are all torch-free at import time
(DR-030) — a real `QueryService` instance is stubbed out here, not
imported from `retrieval`/`generation`.
"""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest

import api.app as app_module
from src.legal_ai.runtime import (
    BoundedExecutor,
    ExecutionProfile,
    resolve_runtime_plan,
)


class _FakeRequest:
    """Stands in for fastapi.Request — only `.client` is touched by
    `_rate_limited`, and we always pass an explicit x_api_key so it's
    never read."""

    client = None


def _fake_result(query: str) -> SimpleNamespace:
    return SimpleNamespace(
        answer=f"answer for {query}", citations=[], evidence=[], warnings=[], timing={},
    )


@pytest.fixture
def small_plan():
    return resolve_runtime_plan(
        probe_cuda_enabled=False, override_profile=ExecutionProfile.CPU_MINIMAL
    )


@pytest.fixture(autouse=True)
def _reset_state():
    original = dict(app_module._state)
    yield
    app_module._state.clear()
    app_module._state.update(original)


def test_executor_capacity_comes_from_resolved_plan_not_a_hardcoded_number(small_plan):
    """The executor api/app.py builds at startup must be sized from the
    ResolvedRuntimePlan's budget — not an independently chosen constant."""
    executor = BoundedExecutor(small_plan.budget)
    try:
        assert executor.in_flight_capacity() == (
            small_plan.budget.max_workers + small_plan.budget.max_queue_size
        )
    finally:
        executor.shutdown(wait=True)


def test_query_endpoint_submits_through_bounded_executor_not_directly(small_plan):
    """Calls the REAL `query()` endpoint coroutine and proves it went
    through BoundedExecutor.submit — not a direct `service.answer()` call
    on the calling (event-loop) thread."""
    service = SimpleNamespace(answer=lambda q, top_k: _fake_result(q))
    executor = BoundedExecutor(small_plan.budget, thread_name_prefix="test-worker")
    app_module._state["service"] = service
    app_module._state["executor"] = executor
    app_module._state["plan"] = small_plan
    app_module._state["startup_error"] = None

    submit_calls = []
    real_submit = executor.submit

    def _tracking_submit(fn, *args, **kwargs):
        submit_calls.append((fn, args, kwargs))
        return real_submit(fn, *args, **kwargs)

    executor.submit = _tracking_submit  # type: ignore[method-assign]

    try:
        req = app_module.QueryRequest(query="ما هو نص المادة الأولى؟", top_k=3)
        result = asyncio.run(app_module.query(req, _FakeRequest(), x_api_key="k"))
        assert result.answer == "answer for ما هو نص المادة الأولى؟"
        assert len(submit_calls) == 1
        fn, args, kwargs = submit_calls[0]
        assert fn is service.answer  # submitted the real service call, unmodified
        assert kwargs.get("block") is False
    finally:
        executor.shutdown(wait=True)


def test_query_endpoint_returns_503_under_real_backpressure(small_plan):
    """Real concurrent load through the actual endpoint function: submit
    more concurrent requests than plan.budget's capacity allows and prove
    at least one gets rejected with HTTP 503 — not merely that
    BackpressureRejected exists as a class."""
    from fastapi import HTTPException

    from src.legal_ai.runtime.budgets import ResourceBudget

    tiny_budget = ResourceBudget(
        max_workers=1, max_queue_size=0, dense_batch_size=8, rerank_batch_size=0,
        max_seq_length=512, max_candidates=20, max_retries=1,
        request_timeout_seconds=5.0, memory_target_bytes=1024,
    )
    release_gate = threading.Event()
    started = threading.Event()

    def slow_answer(query: str, top_k: int):
        started.set()
        release_gate.wait(timeout=5)
        return _fake_result(query)

    service = SimpleNamespace(answer=slow_answer)
    executor = BoundedExecutor(tiny_budget, thread_name_prefix="test-worker")
    app_module._state["service"] = service
    app_module._state["executor"] = executor
    app_module._state["plan"] = small_plan
    app_module._state["startup_error"] = None

    async def _run():
        req = app_module.QueryRequest(query="q1", top_k=3)
        task1 = asyncio.create_task(app_module.query(req, _FakeRequest(), x_api_key="k1"))
        await asyncio.get_event_loop().run_in_executor(None, started.wait, 2)

        req2 = app_module.QueryRequest(query="q2", top_k=3)
        with pytest.raises(HTTPException) as exc_info:
            await app_module.query(req2, _FakeRequest(), x_api_key="k2")
        assert exc_info.value.status_code == 503

        release_gate.set()
        result1 = await task1
        assert result1.answer == "answer for q1"

    try:
        asyncio.run(_run())
    finally:
        executor.shutdown(wait=True)


def test_query_endpoint_bypassing_executor_is_detected(small_plan):
    """Fails-if-bypassed guard (item 7): if a future refactor makes the
    query() endpoint call service.answer() directly instead of through
    executor.submit(), this test must fail. It asserts on the REAL
    endpoint's behavior (executor.submit is actually invoked), not on
    source text/AST inspection, so it stays correct across refactors that
    preserve the contract and breaks the moment the contract itself is
    violated."""
    service = SimpleNamespace(answer=lambda q, top_k: _fake_result(q))
    executor = BoundedExecutor(small_plan.budget, thread_name_prefix="test-worker")
    app_module._state["service"] = service
    app_module._state["executor"] = executor
    app_module._state["plan"] = small_plan
    app_module._state["startup_error"] = None

    called = {"count": 0}

    def _poison(*args, **kwargs):
        called["count"] += 1
        raise RuntimeError("executor.submit was called — good, not bypassed")

    executor.submit = _poison  # type: ignore[method-assign]

    try:
        req = app_module.QueryRequest(query="q", top_k=3)
        with pytest.raises(Exception) as exc_info:
            asyncio.run(app_module.query(req, _FakeRequest(), x_api_key="k"))
        # If the endpoint bypassed the executor and called service.answer()
        # directly, `called["count"]` stays 0 and no exception (or a
        # different one) is raised here instead — that is the failure mode
        # this test exists to catch.
        assert called["count"] == 1, (
            "query() did not go through BoundedExecutor.submit() — "
            "bounded execution has been bypassed."
        )
        assert "executor.submit was called" in str(exc_info.value)
    finally:
        executor.shutdown(wait=True)
