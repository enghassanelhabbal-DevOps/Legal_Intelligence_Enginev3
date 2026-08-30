"""evaluation_case.py — canonical evaluation-case contract.

Per docs/CLAUDE_EXECUTION_MASTER.md's required contract list. Kept minimal
(per that same document's "avoid speculative abstractions" instruction):
this is the record shape a future manual-gold or benchmark case must have
to be usable across retrieval, classification, and citation evaluation —
not a full L1-L10 evaluator (that remains explicitly out of Stage 1 scope,
see docs/EVALUATION_SYSTEM_SPEC.md).

All fields default to the `unknown` sentinel already established in
dataset_manifest.py — an EvaluationCase with unfilled gold fields is a
legitimate, expected state (a case awaiting annotation), not an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

UNKNOWN = "unknown"


class AdjudicationStatus(StrEnum):
    PENDING = "pending"
    SINGLE_REVIEWED = "single_reviewed"
    ADJUDICATED = "adjudicated"
    DISPUTED = "disputed"


@dataclass
class EvaluationCase:
    case_id: str
    source_record_id: str  # traceable back to the source corpus row
    source_dataset: str = UNKNOWN

    question: str | None = None  # populated for retrieval/QA-style cases
    text: str | None = None  # populated for classification/structure-style cases

    # Gold fields — legitimately empty until manually reviewed.
    gold_document_type: str | None = None
    gold_legal_identity: dict[str, Any] | None = None
    gold_structure_presence: bool | None = None
    gold_citation: dict[str, Any] | None = None
    gold_evidence_ids: list[str] = field(default_factory=list)

    review_status: str = AdjudicationStatus.PENDING.value
    reviewer: str | None = None
    adjudication_status: str = AdjudicationStatus.PENDING.value
    notes: str | None = None

    def is_gold_complete(self) -> bool:
        """True only if every gold field has been explicitly set — never
        inferred from a classifier's own prediction."""
        return (
            self.gold_document_type is not None
            and self.review_status != AdjudicationStatus.PENDING.value
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "source_record_id": self.source_record_id,
            "source_dataset": self.source_dataset,
            "question": self.question,
            "text": self.text,
            "gold_document_type": self.gold_document_type,
            "gold_legal_identity": self.gold_legal_identity,
            "gold_structure_presence": self.gold_structure_presence,
            "gold_citation": self.gold_citation,
            "gold_evidence_ids": self.gold_evidence_ids,
            "review_status": self.review_status,
            "reviewer": self.reviewer,
            "adjudication_status": self.adjudication_status,
            "notes": self.notes,
        }


__all__ = ["EvaluationCase", "AdjudicationStatus"]
