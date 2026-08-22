"""evaluation sub-package — retrieval metrics, benchmarks, regression tests.

Public API:
    from src.legal_ai.evaluation import compute_mrr, compute_recall_at_k
    from src.legal_ai.evaluation import RetrievalBaseline, PROTECTED_BASELINE
"""

from src.legal_ai.evaluation.baseline import PROTECTED_BASELINE, RetrievalBaseline
from src.legal_ai.evaluation.metrics import compute_mrr, compute_recall_at_k

__all__ = [
    "compute_mrr",
    "compute_recall_at_k",
    "RetrievalBaseline",
    "PROTECTED_BASELINE",
]
