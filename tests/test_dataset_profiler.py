from __future__ import annotations

import json
from pathlib import Path

from src.legal_ai.evaluation.dataset_profiler import profile_dataset

CORPUS_PATH = Path(__file__).resolve().parents[1] / "legal_documents.json"


def _doc(**overrides) -> dict:
    base = {
        "document_id": "1",
        "jurisdiction": "EG",
        "law_id": "law_a",
        "law_name": "Law A",
        "article_id": "1",
        "raw_text": "نص المادة الأولى من القانون",
        "normalized_text": "نص الماده الاولي من القانون",
        "embedding_text": "المادة 1: نص المادة الأولى من القانون",
    }
    base.update(overrides)
    return base


# --- synthetic fixture scenarios (Stage 1 integration test requirement) ----


def test_duplicate_articles_detected():
    docs = [_doc(document_id="1"), _doc(document_id="2")]  # identical raw_text
    profile = profile_dataset(docs)
    assert profile.duplicate_count == 1


def test_near_duplicate_legal_text_detected_via_normalized_text():
    docs = [
        _doc(document_id="1", raw_text="نص أ", normalized_text="نص مشترك"),
        _doc(document_id="2", raw_text="نص ب", normalized_text="نص مشترك"),
    ]
    profile = profile_dataset(docs)
    assert profile.duplicate_count == 0
    assert profile.near_duplicate_count == 1


def test_amended_versions_are_not_flagged_as_malformed():
    docs = [
        _doc(document_id="1", version_id="v1"),
        _doc(document_id="1v2", version_id="v2", raw_text="نص معدل"),
    ]
    profile = profile_dataset(docs)
    assert profile.malformed_records == 0


def test_multiple_chunks_from_same_law_counted_in_law_distribution():
    docs = [_doc(document_id=str(i), law_id="law_a") for i in range(3)]
    profile = profile_dataset(docs)
    assert profile.law_distribution["law_a"] == 3


def test_different_jurisdictions_tracked_separately():
    docs = [_doc(document_id="1", jurisdiction="EG"), _doc(document_id="2", jurisdiction="SA")]
    profile = profile_dataset(docs)
    assert profile.jurisdiction_distribution == {"EG": 1, "SA": 1}


def test_missing_metadata_recorded_not_guessed():
    docs = [_doc(document_id="1", article_id="")]
    profile = profile_dataset(docs)
    assert profile.citation_completeness == 0.0


def test_mixed_arabic_english_detected():
    docs = [_doc(document_id="1", raw_text="نص Article 5 مختلط")]
    profile = profile_dataset(docs)
    assert profile.language_distribution.get("arabic_english_mixed") == 1


def test_empty_records_counted():
    docs = [_doc(document_id="1", raw_text=""), _doc(document_id="2")]
    profile = profile_dataset(docs)
    assert profile.empty_records == 1


def test_malformed_record_not_a_dict_is_counted_and_does_not_crash():
    docs = [_doc(document_id="1"), "not a dict", 42]
    profile = profile_dataset(docs)
    assert profile.malformed_records == 2
    assert profile.record_count == 3


def test_duplicate_ids_flagged_as_invalid_identifiers():
    docs = [_doc(document_id="1"), _doc(document_id="1", raw_text="different text")]
    profile = profile_dataset(docs)
    assert profile.invalid_identifiers >= 1
    assert any("duplicate" in w.lower() for w in profile.warnings)


def test_content_hash_deterministic_for_same_input():
    docs = [_doc(document_id="1"), _doc(document_id="2", raw_text="نص آخر")]
    p1 = profile_dataset(docs)
    p2 = profile_dataset(docs)
    assert p1.content_hash == p2.content_hash


def test_content_hash_changes_with_content():
    docs_a = [_doc(document_id="1", raw_text="نص أ")]
    docs_b = [_doc(document_id="1", raw_text="نص ب")]
    assert profile_dataset(docs_a).content_hash != profile_dataset(docs_b).content_hash


def test_empty_dataset_does_not_crash():
    profile = profile_dataset([])
    assert profile.record_count == 0
    assert profile.citation_completeness == 0.0


# --- regression coverage against the real 952-article corpus ---------------


def test_real_corpus_profile_regression():
    """Regression test against the existing corpus (not full-corpus mandatory
    for unit tests, but exercised once here per Stage 1 §25)."""
    docs = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    profile = profile_dataset(docs)

    assert profile.record_count == 952
    assert profile.empty_records == 0
    assert profile.malformed_records == 0
    assert profile.jurisdiction_distribution == {"EG": 952}
    assert len(profile.law_distribution) == 2
    # Known, previously-undetected data quality gap surfaced by this profiler:
    # every Penal Code (قانون العقوبات) record has an empty article_id.
    assert profile.missing_required_fields.get("article_id") == 468
    assert profile.citation_completeness < 0.6
