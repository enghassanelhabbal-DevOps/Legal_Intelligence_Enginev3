from __future__ import annotations

import pytest

from src.legal_ai.core.exceptions import DatasetLeakageError, DatasetSplitError
from src.legal_ai.evaluation.leakage import (
    assign_groups,
    check_overlap,
    enforce_no_overlap,
    group_key_for,
)


def _doc(**overrides) -> dict:
    base = {"document_id": "1", "law_id": "law_a", "raw_text": "نص"}
    base.update(overrides)
    return base


# --- grouping -----------------------------------------------------------


def test_group_key_prefers_law_id_over_document_id():
    rec = {"law_id": "law_a", "document_id": "1"}
    assert group_key_for(rec) == "law_id:law_a"


def test_group_key_falls_back_to_document_id_when_no_grouping_field():
    rec = {"document_id": "1", "some_other_field": "x"}
    assert group_key_for(rec) == "document_id:1"


def test_group_key_is_own_group_when_nothing_present():
    rec = {"raw_text": "x"}
    key1 = group_key_for(rec)
    key2 = group_key_for(rec)
    assert key1 == key2  # deterministic, not random


# --- split determinism and safety ----------------------------------------


def test_split_is_deterministic_for_same_seed():
    docs = [_doc(document_id=str(i), law_id=f"law_{i % 5}") for i in range(50)]
    r1 = assign_groups(docs, seed=42)
    r2 = assign_groups(docs, seed=42)
    assert r1.assignments == r2.assignments


def test_split_can_differ_for_different_seed():
    docs = [_doc(document_id=str(i), law_id=f"law_{i}") for i in range(50)]
    r1 = assign_groups(docs, seed=1)
    r2 = assign_groups(docs, seed=999)
    assert r1.assignments != r2.assignments  # not guaranteed in general, but true for this fixture


def test_records_sharing_group_never_split_across_boundaries():
    # 10 records, all same law_id -> must all land in the same split.
    docs = [_doc(document_id=str(i), law_id="shared_law") for i in range(10)]
    result = assign_groups(docs, seed=42)
    assigned_splits = set(result.assignments.values())
    assert len(assigned_splits) == 1


def test_split_rejects_empty_dataset():
    with pytest.raises(DatasetSplitError):
        assign_groups([])


def test_split_rejects_bad_ratios():
    docs = [_doc(document_id="1")]
    with pytest.raises(DatasetSplitError):
        assign_groups(docs, ratios={"train": 0.5, "validation": 0.2})  # sums to 0.7


def test_split_rationale_is_explicit():
    docs = [_doc(document_id=str(i), law_id=f"law_{i % 3}") for i in range(20)]
    result = assign_groups(docs, seed=7)
    assert "law_id" in result.rationale
    assert "seed=7" in result.rationale


# --- overlap / leakage detection -----------------------------------------


def test_no_overlap_reports_clean():
    protected = [_doc(document_id="1", raw_text="نص أ")]
    candidate = [_doc(document_id="2", raw_text="نص ب")]
    report = check_overlap(protected, candidate)
    assert report.is_clean
    assert report.is_meaningful


def test_exact_text_overlap_detected():
    protected = [_doc(document_id="1", raw_text="نص مشترك")]
    candidate = [_doc(document_id="2", raw_text="نص مشترك")]
    report = check_overlap(protected, candidate)
    assert not report.is_clean
    assert report.exact_text_overlap == 1


def test_exact_id_overlap_detected():
    protected = [_doc(document_id="1", raw_text="نص أ")]
    candidate = [_doc(document_id="1", raw_text="نص مختلف تماما")]
    report = check_overlap(protected, candidate)
    assert not report.is_clean
    assert report.exact_id_overlap == 1


def test_mismatched_schema_is_flagged_not_silently_clean():
    """A candidate dataset that doesn't even have the checked fields must not
    report a trustworthy 'clean' result — this was a real bug caught during
    Stage 1 implementation (see docs/research/STAGE_1_REPORT.md)."""
    protected = [_doc(document_id="1", raw_text="نص")]
    candidate = [{"query": "نص", "relevant_document_ids": ["1"]}]  # different schema
    report = check_overlap(protected, candidate)
    assert report.is_clean  # technically true...
    assert not report.is_meaningful  # ...but must be flagged as vacuous
    assert report.warnings


def test_candidate_field_mapping_finds_real_overlap():
    protected = [_doc(document_id="1", raw_text="نص مشترك")]
    candidate = [{"query": "نص مشترك", "relevant_document_ids": ["1"]}]
    report = check_overlap(
        protected,
        candidate,
        candidate_text_field="query",
        candidate_id_field="relevant_document_ids",
    )
    assert report.is_meaningful
    assert not report.is_clean


def test_enforce_no_overlap_raises_on_contamination():
    protected = [_doc(document_id="1", raw_text="نص مشترك")]
    candidate = [_doc(document_id="2", raw_text="نص مشترك")]
    with pytest.raises(DatasetLeakageError):
        enforce_no_overlap(protected, candidate)


def test_enforce_no_overlap_raises_on_vacuous_check_by_default():
    protected = [_doc(document_id="1", raw_text="نص")]
    candidate = [{"query": "نص", "relevant_document_ids": ["1"]}]
    with pytest.raises(DatasetLeakageError):
        enforce_no_overlap(protected, candidate)


def test_enforce_no_overlap_passes_when_genuinely_clean():
    protected = [_doc(document_id="1", raw_text="نص أ")]
    candidate = [_doc(document_id="2", raw_text="نص مختلف تماما وليس له علاقة")]
    enforce_no_overlap(protected, candidate)  # should not raise
