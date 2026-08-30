"""dataset_manifest.py — Canonical dataset manifest contract (Stage 1).

Implements the manifest concept required by DATA_GOVERNANCE.md §3/§17 and
DELIVERY_STAGE_PLAN.md Stage 1: every dataset entering the system must carry
an explicit, versioned, hashable record of what it is, where it came from,
what it may be used for, and whether that has been checked.

Design rule (ARCHITECTURE_CONTRACT.md, DATA_GOVERNANCE.md §3):
    The manifest must distinguish KNOWN / UNKNOWN / NOT_APPLICABLE.
    Missing facts are recorded as UNKNOWN, never guessed.

This module intentionally does not implement every field discussed in
DATA_GOVERNANCE.md (e.g. `legal_systems`, `annotation_method` are deferred —
see docs/research/STAGE_1_REPORT.md "Deferred fields"). It implements the fields
required to make the current 952-article corpus and a second, differently
shaped dataset both profilable, leakage-checkable, and splittable without
per-dataset code, which is the Stage 1 exit criterion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from src.legal_ai.core.exceptions import DatasetManifestError

# ---------------------------------------------------------------------------
# Known / Unknown / Not-applicable sentinel
# ---------------------------------------------------------------------------

UNKNOWN = "unknown"
NOT_APPLICABLE = "not_applicable"


class TaskRole(StrEnum):
    """DATA_GOVERNANCE.md §2 dataset roles."""

    KNOWLEDGE_CORPUS = "knowledge_corpus"
    RETRIEVAL_TUNING = "retrieval_tuning"
    RETRIEVAL_TRAINING = "retrieval_training"
    RETRIEVAL_BENCHMARK = "retrieval_benchmark"
    RERANKER_TUNING = "reranker_tuning"
    RERANKER_TRAINING = "reranker_training"
    RERANKER_BENCHMARK = "reranker_benchmark"
    LEGAL_REASONING = "legal_reasoning"
    REASONING_SFT = "reasoning_sft"
    GENERATION_TRAINING = "generation_training"
    VALIDATION = "validation"
    HELD_OUT_TEST = "held_out_test"
    CHALLENGE_ADVERSARIAL = "challenge_adversarial"
    BENCHMARK_ONLY = "benchmark_only"
    FAILURE_REGRESSION = "failure_regression"


class LicenseStatus(StrEnum):
    KNOWN_PERMISSIVE = "known_permissive"
    KNOWN_RESTRICTED = "known_restricted"
    UNKNOWN = UNKNOWN


class QualityStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"


class LeakageStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    CHECKED_CLEAN = "checked_clean"
    CHECKED_CONTAMINATED = "checked_contaminated"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _stable_hash(payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 over a JSON-canonicalized dict (sorted keys)."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class DatasetManifest:
    """Canonical dataset manifest (DATA_GOVERNANCE.md §3).

    `content_hash` is computed from the actual dataset records at profiling
    time (see dataset_profiler.profile_dataset), not guessed here.
    `manifest_hash` is computed over the manifest's own fields and changes
    whenever manifest metadata changes, independent of dataset content.
    """

    dataset_id: str
    dataset_version: str
    name: str
    description: str = UNKNOWN

    source: str = UNKNOWN
    source_url: str | None = None
    provenance: str = UNKNOWN
    file_sha256: str | None = None  # snapshot hash of the exact analyzed file

    license: str = LicenseStatus.UNKNOWN.value
    license_evidence: str | None = None

    created_at: str | None = None
    ingested_at: str = field(default_factory=_utc_now_iso)

    language: list[str] = field(default_factory=lambda: [UNKNOWN])
    jurisdictions: list[str] = field(default_factory=lambda: [UNKNOWN])
    authority_types: list[str] = field(default_factory=lambda: [UNKNOWN])
    date_coverage: dict[str, str] = field(
        default_factory=lambda: {"start": UNKNOWN, "end": UNKNOWN}
    )

    schema_version: str = "v1"
    record_count: int = 0
    text_fields: list[str] = field(default_factory=list)
    label_fields: list[str] = field(default_factory=list)

    task_roles: list[str] = field(default_factory=list)

    quality_status: str = QualityStatus.PENDING.value
    leakage_status: str = LeakageStatus.NOT_CHECKED.value
    split_strategy: str | None = None

    parent_dataset: str | None = None
    transformations: list[str] = field(default_factory=list)

    content_hash: str = UNKNOWN
    manifest_hash: str = ""

    # Heterogeneous-corpus fields (docs/research/CORPUS_ARCHITECTURE_DIRECTION.md,
    # DR-021+): measured distributions, distinguishable from guesses.
    document_type_distribution: dict[str, int] = field(default_factory=dict)
    category_distribution: dict[str, int] = field(default_factory=dict)
    duplicate_cluster_count: int = 0
    duplicate_cluster_metadata_variant_count: int = 0
    unicode_profile: dict[str, Any] = field(default_factory=dict)
    structure_profile: dict[str, Any] = field(default_factory=dict)
    parser_versions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate_task_roles()
        if not self.manifest_hash:
            self.manifest_hash = self.compute_manifest_hash()

    # -- validation ---------------------------------------------------

    def _validate_task_roles(self) -> None:
        valid = {r.value for r in TaskRole}
        bad = [r for r in self.task_roles if r not in valid]
        if bad:
            raise DatasetManifestError(
                f"Unknown task_roles {bad} for dataset {self.dataset_id!r}; "
                f"must be a subset of {sorted(valid)}"
            )

    def require_license_known_for_training(self) -> None:
        """DATA_GOVERNANCE.md §17: unknown licensing blocks training roles."""
        training_roles = {
            TaskRole.RETRIEVAL_TRAINING.value,
            TaskRole.RERANKER_TRAINING.value,
            TaskRole.REASONING_SFT.value,
            TaskRole.GENERATION_TRAINING.value,
        }
        if self.license == LicenseStatus.UNKNOWN.value and (
            set(self.task_roles) & training_roles
        ):
            raise DatasetManifestError(
                f"Dataset {self.dataset_id!r} has task_roles requiring training use "
                f"but license status is UNKNOWN. Unknown licensing must be resolved "
                f"before a training role is approved (DATA_GOVERNANCE.md §19)."
            )

    # -- hashing --------------------------------------------------------

    def compute_manifest_hash(self) -> str:
        payload = asdict(self)
        payload.pop("manifest_hash", None)
        payload.pop("ingested_at", None)  # ingestion time is not semantic content
        return _stable_hash(payload)

    # -- (de)serialization -----------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path) -> Path:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return out_path

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DatasetManifest:
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in payload.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, path: str | Path) -> DatasetManifest:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)


__all__ = [
    "DatasetManifest",
    "TaskRole",
    "LicenseStatus",
    "QualityStatus",
    "LeakageStatus",
    "UNKNOWN",
    "NOT_APPLICABLE",
]
