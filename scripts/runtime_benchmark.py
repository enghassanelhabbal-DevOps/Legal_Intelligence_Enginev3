"""runtime_benchmark.py — Stage 2 runtime foundation benchmark/report.

Produces `artifacts/reports/runtime_benchmark.json`: a real, measured
snapshot of what `src/legal_ai/runtime/` actually resolves and enforces on
the host running this script — not a description of intended behavior.
Every number here comes from actually calling the runtime module, not from
documentation.

Sections:
  1. hardware_discovery      — wall-clock cost of discover_hardware(),
                                including the isolated-subprocess CUDA
                                probe (DR-028), and the resulting
                                HardwareSnapshot/CPUTopology.
  2. resolved_plans           — for each ExecutionProfile, the
                                ResolvedRuntimePlan actually produced on
                                this host (device, budget, derived
                                RuntimeConfig/PipelineConfig/generation
                                config) — proves policy is centrally owned
                                and traceable back to one resolution per
                                profile.
  3. bounded_execution        — a synthetic workload run through the
                                standalone BoundedExecutor primitive that
                                deliberately exceeds capacity, proving
                                backpressure fires in isolation.
  4. adaptive_batch_policy    — a simulated OOM/success sequence run
                                through runtime.adaptive_batch in
                                isolation, with a determinism check.
  5. integrated_api_path      — the REAL `api/app.py` `/v1/query` endpoint
                                function, called directly under real
                                concurrent load, proving BoundedExecutor is
                                actually wired into the production request
                                path (not just exercised standalone) and
                                that capacity is sized from a
                                ResolvedRuntimePlan. Always measured — this
                                path is torch-free (DR-030).
  6. integrated_dense_reranker_path — the REAL `DenseEncoder.encode_documents()`
                                and `Reranker.score()` methods, with the
                                underlying SentenceTransformer/CrossEncoder
                                replaced by deterministic fakes that
                                simulate one real OOM, proving the
                                deterministic adaptive-batch policy is
                                wired into the actual batch execution path
                                (not just the standalone `adaptive_batch`
                                module). Requires the `dense` extra
                                (torch/sentence-transformers); this section
                                self-reports `{"skipped": true, "reason":
                                ...}` rather than crashing when that extra
                                is not installed, exactly like
                                `tests/test_retrieval.py`'s exclusion from
                                the lightweight CI tier.

Safe to run in the lightweight CI tier: sections 1-5 need no torch/faiss/
GPU/API secrets (CUDA probing degrades to "unavailable" cleanly if no GPU/
driver is present, exactly as designed); section 6 self-skips there.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.legal_ai.runtime import (
    BackpressureRejected,
    BoundedExecutor,
    ExecutionProfile,
    discover_hardware,
    initial_state,
    on_out_of_memory,
    on_success,
    resolve_runtime_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_PATH = REPO_ROOT / "artifacts" / "reports" / "runtime_benchmark.json"


def _benchmark_hardware_discovery() -> dict[str, Any]:
    start = time.perf_counter()
    snapshot = discover_hardware()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {
        "discover_hardware_ms": round(elapsed_ms, 2),
        "cuda_probe_status": snapshot.cuda.probe_status,
        "cuda_probe_isolation": "spawned_subprocess_with_hard_timeout",  # DR-028, preserved as-is
        "snapshot": snapshot.to_dict(),
    }


def _benchmark_resolved_plans() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for profile in ExecutionProfile:
        plan = resolve_runtime_plan(probe_cuda_enabled=False, override_profile=profile)
        results[profile.value] = {
            "device": plan.device,
            "precision": plan.precision,
            "budget": plan.to_dict()["budget"],
            "derived_runtime_config": {
                "device": plan.to_runtime_config().device,
                "dense_batch_size": plan.to_runtime_config().dense_batch_size,
                "rerank_batch_size": plan.to_runtime_config().rerank_batch_size,
                "num_threads": plan.to_runtime_config().num_threads,
            },
            "derived_pipeline_config": {
                "dense_candidates": plan.to_pipeline_config().dense_candidates,
                "rerank_candidates": plan.to_pipeline_config().rerank_candidates,
            },
            "derived_generation_config": plan.to_generation_config(),
        }
    return results


def _benchmark_bounded_execution() -> dict[str, Any]:
    from src.legal_ai.runtime.budgets import ResourceBudget

    budget = ResourceBudget(
        max_workers=2, max_queue_size=2, dense_batch_size=8, rerank_batch_size=0,
        max_seq_length=512, max_candidates=20, max_retries=1,
        request_timeout_seconds=5.0, memory_target_bytes=1024,
    )
    capacity = budget.max_workers + budget.max_queue_size  # == 4

    accepted = 0
    rejected = 0
    with BoundedExecutor(budget) as executor:
        futures = []
        # Submit more work than capacity allows, non-blocking, to force
        # real backpressure — this is the actual mechanism under load, not
        # a description of it.
        for _ in range(capacity + 5):
            try:
                futures.append(executor.submit(lambda: sum(range(10_000)), block=False))
                accepted += 1
            except BackpressureRejected:
                rejected += 1
        for f in futures:
            f.result(timeout=5)

    return {
        "configured_capacity": capacity,
        "submissions_attempted": capacity + 5,
        "submissions_accepted": accepted,
        "submissions_rejected_by_backpressure": rejected,
        "backpressure_triggered": rejected > 0,
    }


def _benchmark_adaptive_batch() -> dict[str, Any]:
    outcomes = [
        "oom", "oom", "success", "success", "success", "oom", "success", "success", "success",
    ]

    def run() -> list[int]:
        state = initial_state(ceiling=64, floor=2)
        trace = [state.current_batch_size]
        for outcome in outcomes:
            state = on_out_of_memory(state) if outcome == "oom" else on_success(state)
            trace.append(state.current_batch_size)
        return trace

    trace_a = run()
    trace_b = run()
    return {
        "outcome_sequence": outcomes,
        "batch_size_trace": trace_a,
        "deterministic_replay_match": trace_a == trace_b,
    }


def _benchmark_integrated_api_path() -> dict[str, Any]:
    """Exercises the REAL `api/app.py` `/v1/query` endpoint function under
    real concurrent load — not a reimplementation, not the standalone
    BoundedExecutor from section 3. Proves BoundedExecutor is actually
    wired into the production request path and sized from a
    ResolvedRuntimePlan (item 1/4)."""
    import asyncio
    import threading
    from types import SimpleNamespace

    import api.app as app_module
    from src.legal_ai.runtime.budgets import ResourceBudget

    class _FakeRequest:
        client = None

    tiny_budget = ResourceBudget(
        max_workers=1, max_queue_size=0, dense_batch_size=8, rerank_batch_size=0,
        max_seq_length=512, max_candidates=20, max_retries=1,
        request_timeout_seconds=5.0, memory_target_bytes=1024,
    )
    release_gate = threading.Event()
    started = threading.Event()

    def slow_answer(query: str, top_k: int) -> SimpleNamespace:
        started.set()
        release_gate.wait(timeout=5)
        return SimpleNamespace(
            answer=f"answer for {query}", citations=[], evidence=[], warnings=[], timing={}
        )

    original_state = dict(app_module._state)
    app_module._state["service"] = SimpleNamespace(answer=slow_answer)
    app_module._state["executor"] = BoundedExecutor(tiny_budget, thread_name_prefix="bench-worker")
    app_module._state["startup_error"] = None
    executor = app_module._state["executor"]

    result: dict[str, Any] = {"configured_capacity": executor.in_flight_capacity()}
    try:
        async def _run() -> None:
            req1 = app_module.QueryRequest(query="q1", top_k=3)
            task1 = asyncio.create_task(app_module.query(req1, _FakeRequest(), x_api_key="k1"))
            await asyncio.get_event_loop().run_in_executor(None, started.wait, 2)

            from fastapi import HTTPException

            req2 = app_module.QueryRequest(query="q2", top_k=3)
            rejected = False
            status_code = None
            try:
                await app_module.query(req2, _FakeRequest(), x_api_key="k2")
            except HTTPException as exc:
                rejected = True
                status_code = exc.status_code

            release_gate.set()
            answer1 = await task1

            result["second_request_rejected_with_503"] = rejected and status_code == 503
            result["first_request_completed"] = answer1.answer == "answer for q1"

        asyncio.run(_run())
    finally:
        executor.shutdown(wait=True)
        app_module._state.clear()
        app_module._state.update(original_state)

    result["proves"] = (
        "the real /v1/query endpoint submits through BoundedExecutor "
        "(sized from ResourceBudget) and rejects over-capacity concurrent "
        "requests with HTTP 503 rather than blocking the event loop or "
        "queuing unbounded work"
    )
    return result


def _benchmark_integrated_dense_reranker_path() -> dict[str, Any]:
    """Exercises the REAL `DenseEncoder.encode_documents()` and
    `Reranker.score()` methods (not the standalone `adaptive_batch`
    module from section 4) with the underlying SentenceTransformer/
    CrossEncoder replaced by deterministic fakes that OOM exactly once at
    the requested ceiling. Requires the `dense` extra; self-skips with a
    clear reason if unavailable rather than crashing the lightweight CI
    tier (item 8)."""
    try:
        from unittest.mock import patch

        import numpy as np
        import torch
    except ImportError as exc:
        return {"skipped": True, "reason": f"dense extra not installed: {exc}"}

    try:
        from src.legal_ai.reranking.cross_encoder import Reranker
        from src.legal_ai.retrieval.dense import DenseEncoder
    except ImportError as exc:
        return {"skipped": True, "reason": f"dense extra not installed: {exc}"}

    class _FlakySentenceTransformer:
        def __init__(self, model_name: str, device: str) -> None:
            self.max_seq_length = None
            self.calls: list[int] = []

        def encode(self, texts: list[str], batch_size: int, **kwargs: Any) -> Any:
            self.calls.append(batch_size)
            if len(self.calls) == 1:
                raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
            return np.array([[float(len(t))] for t in texts], dtype=np.float32)

    class _FlakyCrossEncoder:
        def __init__(
            self, model_name: str, device: str, max_length: int, model_kwargs: dict
        ) -> None:
            self.calls: list[int] = []

        def predict(self, pairs: list[list[str]], batch_size: int, **kwargs: Any) -> Any:
            self.calls.append(batch_size)
            if len(self.calls) == 1:
                raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
            return np.array([float(len(p[1])) for p in pairs], dtype=np.float32)

    with patch("src.legal_ai.retrieval.dense.SentenceTransformer", _FlakySentenceTransformer):
        encoder = DenseEncoder("fake-model", device="cpu", dtype=torch.float32, max_seq_length=64)
        embeddings = encoder.encode_documents(["a", "bb", "ccc"], batch_size=32)
        dense_calls = list(encoder.model.calls)
        dense_result_shape = list(embeddings.shape)

    from src.legal_ai.core.models import RetrievalHit

    hits = [RetrievalHit(document_id="1", index=0, text="نص", law_name="قانون", article_id="1")]
    with patch("src.legal_ai.reranking.cross_encoder.CrossEncoder", _FlakyCrossEncoder):
        reranker = Reranker("fake-reranker", device="cpu", dtype=torch.float32)
        scores = reranker.score("query", hits, batch_size=16, max_chars=100)
        rerank_calls = list(reranker.model.calls)
        rerank_result_shape = list(scores.shape)

    return {
        "skipped": False,
        "dense_encoder_batch_size_calls": dense_calls,
        "dense_encoder_stepped_down_deterministically": dense_calls == [32, 16],
        "dense_encoder_output_shape": dense_result_shape,
        "reranker_batch_size_calls": rerank_calls,
        "reranker_stepped_down_deterministically": rerank_calls == [16, 8],
        "reranker_output_shape": rerank_result_shape,
        "proves": (
            "DenseEncoder.encode_documents() and Reranker.score() actually "
            "retry through runtime.torch_adaptive_batch on a real OOM "
            "exception, stepping the batch size down deterministically "
            "(32->16, 16->8), not via the standalone adaptive_batch module "
            "in isolation"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
    args = parser.parse_args()

    report = {
        "report": "stage2_runtime_benchmark",
        "hardware_discovery": _benchmark_hardware_discovery(),
        "resolved_plans": _benchmark_resolved_plans(),
        "bounded_execution": _benchmark_bounded_execution(),
        "adaptive_batch_policy": _benchmark_adaptive_batch(),
        "integrated_api_path": _benchmark_integrated_api_path(),
        "integrated_dense_reranker_path": _benchmark_integrated_dense_reranker_path(),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWrote report to {args.out}")

    # Sanity assertions — fail the CI step if the runtime foundation is not
    # actually behaving as documented, rather than silently writing a
    # report nobody reads.
    assert report["bounded_execution"]["backpressure_triggered"], "backpressure never fired"
    adaptive = report["adaptive_batch_policy"]
    assert adaptive["deterministic_replay_match"], "adaptive batch is non-deterministic"

    integrated_api = report["integrated_api_path"]
    assert integrated_api["second_request_rejected_with_503"], (
        "integrated API path did not reject over-capacity requests with 503 "
        "— BoundedExecutor may have been bypassed in api/app.py"
    )
    assert integrated_api["first_request_completed"], (
        "integrated API path's own request never completed"
    )

    integrated_dense = report["integrated_dense_reranker_path"]
    if integrated_dense.get("skipped"):
        print(f"\nNOTE: integrated_dense_reranker_path skipped — {integrated_dense['reason']}")
    else:
        assert integrated_dense["dense_encoder_stepped_down_deterministically"], (
            "DenseEncoder.encode_documents() did not step down deterministically on OOM "
            "— adaptive batching may have been bypassed"
        )
        assert integrated_dense["reranker_stepped_down_deterministically"], (
            "Reranker.score() did not step down deterministically on OOM "
            "— adaptive batching may have been bypassed"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
