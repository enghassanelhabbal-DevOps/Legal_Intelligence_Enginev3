"""quality_gate.py — Fail the build if measured retrieval quality regresses.

Reads the report produced by `scripts/regression_harness.py` (real corpus,
real BM25 engine — see that script's docstring) and compares it against
`SELF_RETRIEVAL_SMOKE_BASELINE` in `src/legal_ai/evaluation/baseline.py`.

Exit code 0  -> pass (safe to merge)
Exit code 1  -> regression detected (block the merge)
Exit code 2  -> report missing/invalid (run regression_harness.py first)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.legal_ai.evaluation.baseline import SELF_RETRIEVAL_SMOKE_BASELINE, RetrievalBaseline


def load_report(path: Path) -> RetrievalBaseline:
    if not path.exists():
        print(
            f"ERROR: regression report not found at {path}. "
            "Run scripts/regression_harness.py first."
        )
        sys.exit(2)
    data = json.loads(path.read_text(encoding="utf-8"))
    m = data["metrics"]
    return RetrievalBaseline(
        mrr=m["MRR"],
        recall_at_1=m["Recall@1"],
        recall_at_3=m["Recall@3"],
        recall_at_5=m["Recall@5"],
        recall_at_10=m["Recall@10"],
        description=(
            f"measured ({data.get('corpus_documents')} docs, "
            f"{data.get('eval_set_size')} queries)"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="artifacts/reports/regression_baseline.json")
    parser.add_argument("--tolerance", type=float, default=0.01)
    args = parser.parse_args()

    measured = load_report(Path(args.report))
    baseline = SELF_RETRIEVAL_SMOKE_BASELINE

    checks = {
        "MRR": (measured.mrr, baseline.mrr),
        "Recall@1": (measured.recall_at_1, baseline.recall_at_1),
        "Recall@3": (measured.recall_at_3, baseline.recall_at_3),
        "Recall@5": (measured.recall_at_5, baseline.recall_at_5),
        "Recall@10": (measured.recall_at_10, baseline.recall_at_10),
    }

    print(f"Baseline floor: {baseline.description}")
    print(f"{'Metric':<12}{'Measured':>10}{'Floor':>10}{'Delta':>10}  Status")
    all_ok = True
    for name, (got, floor) in checks.items():
        delta = got - floor
        ok = got >= floor - args.tolerance
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(f"{name:<12}{got:>10.4f}{floor:>10.4f}{delta:>+10.4f}  {status}")

    if not all_ok:
        print("\nQUALITY GATE FAILED — retrieval regression detected against the real corpus.")
        sys.exit(1)

    print("\nQuality gate passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
