from __future__ import annotations

import pytest

from src.legal_ai.evaluation.dataset_adapters import (
    ADAPTERS,
    apply_adapter,
    dataflare_egypt_legal_corpus_adapter,
    identity_adapter,
)
from src.legal_ai.evaluation.dataset_profiler import profile_dataset


def test_identity_adapter_passes_through_unchanged():
    rec = {"document_id": "1", "raw_text": "نص"}
    assert identity_adapter(rec) is rec


def test_dataflare_adapter_maps_canonical_fields():
    rec = {
        "law_name": "قانون العقوبات",
        "categories": ["جنائي"],
        "text": "نص المادة",
        "tokens": 10,
    }
    mapped = dataflare_egypt_legal_corpus_adapter(rec)
    assert mapped["raw_text"] == "نص المادة"
    assert mapped["law_id"] == "قانون العقوبات"
    assert mapped["law_name"] == "قانون العقوبات"
    assert mapped["jurisdiction"] == "EG"
    assert mapped["jurisdiction_source"] == "dataset_name_declared"
    assert mapped["source"] == "dataflare/egypt-legal-corpus"


def test_dataflare_adapter_article_id_is_unknown_not_guessed():
    rec = {"law_name": "قانون", "text": "نص طويل بلا حدود مواد واضحة", "tokens": 5}
    mapped = dataflare_egypt_legal_corpus_adapter(rec)
    assert mapped["article_id"] is None


def test_dataflare_adapter_derives_stable_content_based_id():
    rec = {"law_name": "قانون العقوبات", "text": "نص ثابت", "tokens": 5}
    id1 = dataflare_egypt_legal_corpus_adapter(rec)["document_id"]
    id2 = dataflare_egypt_legal_corpus_adapter(rec)["document_id"]
    assert id1 == id2
    assert id1.startswith("content:")  # never presented as a source-original id


def test_dataflare_adapter_different_content_yields_different_id():
    rec_a = {"law_name": "قانون", "text": "نص أ", "tokens": 5}
    rec_b = {"law_name": "قانون", "text": "نص ب", "tokens": 5}
    id_a = dataflare_egypt_legal_corpus_adapter(rec_a)["document_id"]
    id_b = dataflare_egypt_legal_corpus_adapter(rec_b)["document_id"]
    assert id_a != id_b


def test_unknown_adapter_name_raises():
    with pytest.raises(ValueError):
        apply_adapter([{}], "nonexistent_adapter")


def test_apply_adapter_dataflare_end_to_end_is_profilable():
    """A second dataset in a different schema must be profilable without new
    pipeline code — this is the Stage 1 exit criterion this test enforces."""
    raw_records = [
        {
            "law_name": "قانون العقوبات",
            "categories": ["جنائي"],
            "text": "المادة 1 - نص تجريبي للمادة الأولى.",
            "tokens": 12,
        },
        {
            "law_name": "قانون التجارة",
            "categories": ["تجاري"],
            "text": "المادة 1 - نص تجريبي عن الشركات.",
            "tokens": 10,
        },
    ]
    mapped = apply_adapter(raw_records, "dataflare_egypt_legal_corpus")
    profile = profile_dataset(mapped)
    assert profile.record_count == 2
    assert profile.jurisdiction_distribution == {"EG": 2}
    assert len(profile.law_distribution) == 2


def test_adapter_registry_contains_expected_names():
    assert "identity" in ADAPTERS
    assert "dataflare_egypt_legal_corpus" in ADAPTERS
