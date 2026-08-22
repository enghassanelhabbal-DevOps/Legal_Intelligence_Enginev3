"""baseline.py — Protected retrieval baseline definition.

The values here are the LOCKED baseline from ARCHITECTURE_CONTRACT.md.
Any change to retrieval or reranking must be measured against these numbers
and the results reported before merging.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalBaseline:
    """Snapshot of known-good retrieval performance metrics."""

    mrr: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    description: str = ""

    def as_dict(self) -> dict[str, float]:
        return {
            "MRR": self.mrr,
            "Recall@1": self.recall_at_1,
            "Recall@3": self.recall_at_3,
            "Recall@5": self.recall_at_5,
            "Recall@10": self.recall_at_10,
        }

    def check(self, measured: RetrievalBaseline, tol: float = 0.005) -> bool:
        """Return True if *measured* is within *tol* of this baseline on all metrics."""
        return all([
            measured.mrr >= self.mrr - tol,
            measured.recall_at_1 >= self.recall_at_1 - tol,
            measured.recall_at_3 >= self.recall_at_3 - tol,
            measured.recall_at_5 >= self.recall_at_5 - tol,
            measured.recall_at_10 >= self.recall_at_10 - tol,
        ])


# LOCKED — historical claim from ARCHITECTURE_CONTRACT.md.
#
# ⚠️ PROVENANCE NOTE (added during the Aug 2026 consolidation review): the
# harness/script that originally produced these five numbers was not found
# in the repository at review time — the only evaluation code present
# (scripts/regression_harness.py, scripts/quality_gate.py,
# tests/test_regression_quality.py) tested a 3-sentence synthetic fixture
# using a legacy retrieval implementation, not this pipeline. These numbers
# are kept here as the team's documented historical claim and as a target
# to eventually re-validate with a proper human-labeled evaluation set, but
# they are NOT currently used as an enforced CI gate — see
# SELF_RETRIEVAL_SMOKE_BASELINE below for what CI actually checks today.
PROTECTED_BASELINE = RetrievalBaseline(
    mrr=0.835,
    recall_at_1=0.75,
    recall_at_3=0.90,
    recall_at_5=0.95,
    recall_at_10=1.00,
    description="BGE-M3 + BM25 + BGE-reranker-v2-m3, dense-preserving fusion, alpha=0.75 "
    "(historical claim — original evaluation script/dataset not found; unverified).",
)

# ACTUALLY MEASURED — produced by `scripts/regression_harness.py` against the
# real 952-article corpus using a self-retrieval smoke evaluation set (see
# `scripts/build_eval_set.py` for methodology and its limits). This is a
# regression *floor*, deliberately set a few points below the first real
# measurement (MRR 0.975 / Recall@1 0.9625 on 2026-08-19, BM25-only), so CI
# fails on a real regression without being flaky on minor score noise.
# Self-retrieval is an easier task than genuine user queries, so these
# thresholds are intentionally high relative to PROTECTED_BASELINE above —
# do not compare the two numbers directly, they measure different things.
SELF_RETRIEVAL_SMOKE_BASELINE = RetrievalBaseline(
    mrr=0.90,
    recall_at_1=0.85,
    recall_at_3=0.92,
    recall_at_5=0.93,
    recall_at_10=0.93,
    description="BM25-only self-retrieval smoke gate against the real corpus "
    "(scripts/regression_harness.py + scripts/build_eval_set.py).",
)

__all__ = ["RetrievalBaseline", "PROTECTED_BASELINE", "SELF_RETRIEVAL_SMOKE_BASELINE"]
