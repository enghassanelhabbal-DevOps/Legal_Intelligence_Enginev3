"""execution.py — bounded worker pool with a bounded submission queue.

RESOURCE_RELIABILITY_SPEC.md §4/§10: worker count AND queued work must
both be bounded — "no unbounded task spawning". This is not automatic:
`concurrent.futures.ThreadPoolExecutor` only bounds `max_workers` (how
many tasks run concurrently); its internal work queue has no `maxsize`,
so calling `.submit()` past `max_workers` in-flight tasks still succeeds
immediately and silently accumulates unbounded pending work in memory —
exactly the failure mode this module exists to prevent.

`BoundedExecutor` closes that gap with an admission-control semaphore
sized to `max_workers + max_queue_size`: once that many tasks are either
running or queued, further `submit()` calls either block (if the caller
opts in) or raise `BackpressureRejected` — there is no third option where
work silently piles up unbounded.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

from src.legal_ai.runtime.budgets import ResourceBudget

T = TypeVar("T")


class BackpressureRejected(RuntimeError):
    """Raised by `BoundedExecutor.submit(..., block=False)` when both the
    worker pool and the bounded queue are already full. The caller must
    handle this explicitly (e.g. surface a 429/backoff to its own caller)
    — it is never silently retried in a loop here (RESOURCE_RELIABILITY_
    SPEC.md §10: no unbounded retries)."""


class BoundedExecutor:
    """A `ThreadPoolExecutor` gated by a bounded admission semaphore so
    that (running + queued) work is a hard, finite ceiling — never
    unbounded queuing, regardless of how fast the caller submits work.
    """

    def __init__(
        self, budget: ResourceBudget, *, thread_name_prefix: str = "bounded-worker"
    ) -> None:
        if budget.max_workers < 1:
            raise ValueError(f"budget.max_workers must be >= 1, got {budget.max_workers}")
        if budget.max_queue_size < 0:
            raise ValueError(f"budget.max_queue_size must be >= 0, got {budget.max_queue_size}")
        self.budget = budget
        self._executor = ThreadPoolExecutor(
            max_workers=budget.max_workers, thread_name_prefix=thread_name_prefix
        )
        self._admission = threading.BoundedSemaphore(budget.max_workers + budget.max_queue_size)

    def submit(
        self, fn: Callable[..., T], *args: object, block: bool = False, **kwargs: object
    ) -> Future[T]:
        """Submit `fn(*args, **kwargs)` for bounded execution.

        `block=False` (default): raise `BackpressureRejected` immediately
        if the pool+queue are already at capacity — the caller decides
        what "reject" means for it (surface an error, shed load, etc.).
        `block=True`: block the calling thread until a slot frees up
        rather than rejecting — useful for a producer that should simply
        slow down rather than fail.
        """
        acquired = self._admission.acquire(blocking=block)
        if not acquired:
            raise BackpressureRejected(
                f"BoundedExecutor at capacity: {self.budget.max_workers} workers + "
                f"{self.budget.max_queue_size} queue slots all in use."
            )
        try:
            future = self._executor.submit(fn, *args, **kwargs)
        except BaseException:
            self._admission.release()
            raise
        future.add_done_callback(lambda _f: self._admission.release())
        return future

    def in_flight_capacity(self) -> int:
        """Total admissible in-flight work (running + queued) — the hard
        ceiling this executor enforces."""
        return self.budget.max_workers + self.budget.max_queue_size

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    def __enter__(self) -> BoundedExecutor:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.shutdown(wait=True)


__all__ = ["BoundedExecutor", "BackpressureRejected"]
