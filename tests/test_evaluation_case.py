from __future__ import annotations

from src.legal_ai.domain.evaluation_case import AdjudicationStatus, EvaluationCase


def test_minimal_case_defaults_to_pending_and_empty_gold():
    case = EvaluationCase(case_id="c1", source_record_id="r1")
    assert case.review_status == AdjudicationStatus.PENDING.value
    assert case.gold_document_type is None
    assert case.is_gold_complete() is False


def test_gold_complete_requires_both_field_and_reviewed_status():
    case = EvaluationCase(case_id="c1", source_record_id="r1")
    case.gold_document_type = "statute"
    assert case.is_gold_complete() is False  # still pending review status
    case.review_status = AdjudicationStatus.ADJUDICATED.value
    assert case.is_gold_complete() is True


def test_gold_evidence_ids_defaults_to_empty_list_not_none():
    case = EvaluationCase(case_id="c1", source_record_id="r1")
    assert case.gold_evidence_ids == []


def test_to_dict_shape():
    case = EvaluationCase(case_id="c1", source_record_id="r1")
    d = case.to_dict()
    assert d["case_id"] == "c1"
    assert d["source_record_id"] == "r1"
    assert "gold_citation" in d
