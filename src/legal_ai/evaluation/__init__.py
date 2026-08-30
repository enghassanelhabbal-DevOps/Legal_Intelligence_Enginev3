"""evaluation sub-package — retrieval metrics, benchmarks, dataset intake.

Public API:
    from src.legal_ai.evaluation import compute_mrr, compute_recall_at_k
    from src.legal_ai.evaluation import RetrievalBaseline, PROTECTED_BASELINE
    from src.legal_ai.evaluation import DatasetManifest, TaskRole
    from src.legal_ai.evaluation import profile_dataset
    from src.legal_ai.evaluation import assign_groups, check_overlap, enforce_no_overlap
"""

from src.legal_ai.evaluation.baseline import PROTECTED_BASELINE, RetrievalBaseline
from src.legal_ai.evaluation.dataset_manifest import (
    DatasetManifest,
    LeakageStatus,
    LicenseStatus,
    QualityStatus,
    TaskRole,
)
from src.legal_ai.evaluation.dataset_profiler import QualityProfile, profile_dataset
from src.legal_ai.evaluation.leakage import (
    OverlapReport,
    SplitResult,
    assign_groups,
    check_overlap,
    enforce_no_overlap,
    group_key_for,
)
from src.legal_ai.evaluation.metrics import compute_mrr, compute_recall_at_k

__all__ = [
    "compute_mrr",
    "compute_recall_at_k",
    "RetrievalBaseline",
    "PROTECTED_BASELINE",
    "DatasetManifest",
    "TaskRole",
    "LicenseStatus",
    "QualityStatus",
    "LeakageStatus",
    "QualityProfile",
    "profile_dataset",
    "SplitResult",
    "OverlapReport",
    "assign_groups",
    "check_overlap",
    "enforce_no_overlap",
    "group_key_for",
]
