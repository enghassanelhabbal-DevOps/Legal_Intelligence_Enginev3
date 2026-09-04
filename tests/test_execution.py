from __future__ import annotations

import threading
import time

import pytest

from src.legal_ai.runtime.budgets import ResourceBudget
from src.legal_ai.runtime.execution import BackpressureRejected, BoundedExecutor


def _budget(max_workers: int, max_queue_size: int) -> ResourceBudget:
    return ResourceBudget(
        max_workers=max_workers,
        max_queue_size=max_queue_size,
        dense_batch_size=8,
        rerank_batch_size=0,
        max_seq_length=512,
        max_candidates=20,
        max_retries=1,
        request_timeout_seconds=5.0,
        memory_target_bytes=1024,
    )


def test_rejects_invalid_budgets():
    with pytest.raises(ValueError):
        BoundedExecutor(_budget(max_workers=0, max_queue_size=1))
    with pytest.raises(ValueError):
        BoundedExecutor(_budget(max_workers=1, max_queue_size=-1))


def test_in_flight_capacity_is_workers_plus_queue():
    executor = BoundedExecutor(_budget(max_workers=2, max_queue_size=3))
    try:
        assert executor.in_flight_capacity() == 5
    finally:
        executor.shutdown(wait=True)


def test_submits_up_to_capacity_and_rejects_beyond_it_when_not_blocking():
    """1 worker + 1 queue slot = capacity 2. Hold the worker busy with a
    blocking task, fill the one queue slot, then a third non-blocking
    submit must be rejected rather than silently queued unbounded."""
    release_gate = threading.Event()
    started = threading.Event()

    def blocking_task():
        started.set()
        release_gate.wait(timeout=5)
        return "done"

    executor = BoundedExecutor(_budget(max_workers=1, max_queue_size=1))
    try:
        f1 = executor.submit(blocking_task)  # occupies the 1 worker
        started.wait(timeout=2)
        f2 = executor.submit(blocking_task)  # occupies the 1 queue slot
        with pytest.raises(BackpressureRejected):
            executor.submit(blocking_task, block=False)  # capacity full -> rejected

        release_gate.set()
        assert f1.result(timeout=5) == "done"
        assert f2.result(timeout=5) == "done"
    finally:
        executor.shutdown(wait=True)


def test_capacity_frees_up_after_task_completes():
    executor = BoundedExecutor(_budget(max_workers=1, max_queue_size=0))
    try:
        f1 = executor.submit(lambda: 1 + 1)
        assert f1.result(timeout=5) == 2
        # Capacity must have been released by the done-callback — a second
        # submit right after must succeed without blocking or rejecting.
        f2 = executor.submit(lambda: 2 + 2, block=False)
        assert f2.result(timeout=5) == 4
    finally:
        executor.shutdown(wait=True)


def test_blocking_submit_waits_instead_of_rejecting():
    release_gate = threading.Event()
    started = threading.Event()

    def blocking_task():
        started.set()
        release_gate.wait(timeout=5)
        return "done"

    executor = BoundedExecutor(_budget(max_workers=1, max_queue_size=0))
    try:
        f1 = executor.submit(blocking_task)
        started.wait(timeout=2)

        result_holder: dict[str, object] = {}

        def blocked_submitter():
            future = executor.submit(lambda: "second", block=True)
            result_holder["future"] = future

        t = threading.Thread(target=blocked_submitter)
        t.start()
        time.sleep(0.05)
        assert "future" not in result_holder  # still blocked, capacity is full

        release_gate.set()
        f1.result(timeout=5)
        t.join(timeout=5)
        assert result_holder["future"].result(timeout=5) == "second"
    finally:
        executor.shutdown(wait=True)


def test_exception_in_submitted_fn_still_releases_capacity():
    executor = BoundedExecutor(_budget(max_workers=1, max_queue_size=0))
    try:
        def boom():
            raise ValueError("boom")

        f1 = executor.submit(boom)
        with pytest.raises(ValueError):
            f1.result(timeout=5)
        # Capacity must be released even though the task raised.
        f2 = executor.submit(lambda: "ok", block=False)
        assert f2.result(timeout=5) == "ok"
    finally:
        executor.shutdown(wait=True)


def test_context_manager_shuts_down_on_exit():
    with BoundedExecutor(_budget(max_workers=1, max_queue_size=0)) as executor:
        f = executor.submit(lambda: 42)
        assert f.result(timeout=5) == 42
    # Executor is shut down; submitting after exit must raise (standard
    # ThreadPoolExecutor behavior — verifies shutdown actually happened).
    with pytest.raises(RuntimeError):
        executor.submit(lambda: 1, block=False)
