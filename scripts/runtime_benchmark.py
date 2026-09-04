"""runtime_benchmark.py — Stage 2 runtime foundation benchmark/report.

Produces `artifacts/reports/runtime_benchmark.json`: a real, measured
snapshot of what `src/legal_ai/runtime/` actually resolves and enforces on
the host running this script — not a description of intended behavior.
Every number here comes from actually calling the runtime module, not from
documentation.

Sections:
  1. hardware_discovery   — wall-clock cost of discover_hardware(), including
                             the isolated-subprocess CUDA probe (DR-028),
                             and the resulting HardwareSnapshot/CPUTopology.
  2. resolved_plans        — for each ExecutionProfile, the ResolvedRuntimePlan
                             actually produced on this host (device, budget,
                             derived RuntimeConfig/PipelineConfig/generation
                             config) — proves policy is centrally owned and
                             traceable back to one resolution per profile.
  3. bounded_execution     — a synthetic workload run through BoundedExecutor
                             that deliberately exceeds capacity, to prove
                             backpressure (BackpressureRejected) actually
                             fires rather than silently queuing unbounded work.
  4. adaptive_batch_policy — a simulated OOM/success sequence run through
                             runtime.adaptive_batch, with a determinism check
                             (replaying the same sequence twice and comparing).

Safe to run in the lightweight CI tier: no torch/faiss/GPU/API secrets
required (CUDA probing degrades to "unavailable" cleanly if no GPU/driver
is present, exactly as designed).
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
