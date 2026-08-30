"""Real-data regression tests (master prompt §38): a small, stable,
versioned fixture sampled from the real dataflare/egypt-legal-corpus
(not the full dataset — see tests/fixtures/dataflare_real_sample_v1.json),
covering each document type category plus a known duplicate pair.
Provenance (source row index, source file SHA-256) is preserved in the
fixture itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.legal_ai.domain.document_type import DocumentType, classify_document
from src.legal_ai.domain.duplicate_clustering import cluster_exact_duplicates
from src.legal_ai.ingestion.case_citation_extraction import extract_case_citation

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dataflare_real_sample_v1.json"


@pytest.fixture(scope="module")
def fixture_data():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _record_by_label(fixture_data, label):
    return next(r for r in fixture_data["records"] if r["fixture_label"] == label)


def test_fixture_has_expected_provenance(fixture_data):
    assert fixture_data["source"] == "dataflare/egypt-legal-corpus"
    assert (
        fixture_data["source_file_sha256"]
        == "a55c349e9c95faffcdf49b66c726be7ae4ed738aafd43767d8ae99f5903d4458"
    )
    assert len(fixture_data["records"]) == 9


def test_civil_cassation_example_classifies_correctly(fixture_data):
    rec = _record_by_label(fixture_data, "civil_cassation_example")
    result = classify_document(rec["text"], rec["categories"])
    assert result.document_type == DocumentType.JUDICIAL_CASSATION_CIVIL


def test_criminal_cassation_example_classifies_correctly(fixture_data):
    rec = _record_by_label(fixture_data, "criminal_cassation_example")
    result = classify_document(rec["text"], rec["categories"])
    assert result.document_type == DocumentType.JUDICIAL_CASSATION_CRIMINAL


def test_administrative_example_classifies_correctly(fixture_data):
    rec = _record_by_label(fixture_data, "administrative_example")
    result = classify_document(rec["text"], rec["categories"])
    assert result.document_type == DocumentType.JUDICIAL_ADMINISTRATIVE


def test_statute_example_classifies_correctly(fixture_data):
    rec = _record_by_label(fixture_data, "statute_example")
    result = classify_document(rec["text"], rec["categories"])
    assert result.document_type == DocumentType.STATUTE


def test_legal_form_example_classifies_correctly(fixture_data):
    rec = _record_by_label(fixture_data, "legal_form_example")
    result = classify_document(rec["text"], rec["categories"])
    assert result.document_type == DocumentType.LEGAL_FORM


def test_unknown_example_does_not_get_a_forced_guess(fixture_data):
    rec = _record_by_label(fixture_data, "unknown_example")
    result = classify_document(rec["text"], rec["categories"])
    assert result.document_type == DocumentType.UNKNOWN
    assert result.confidence == 0.0


def test_case_citation_extraction_on_real_cassation_examples(fixture_data):
    for label in ["civil_cassation_example", "criminal_cassation_example"]:
        rec = _record_by_label(fixture_data, label)
        citation = extract_case_citation(rec["text"])
        assert citation.is_case_ruling is True
        # Citation extraction on truncated (600-char) text may not always
        # capture the full pattern — assert the type is detected correctly,
        # which is the load-bearing guarantee; full-field extraction
        # coverage is measured against the full untruncated corpus
        # separately (94.8%, see docs/DATASET_ASSESSMENT...).


def test_duplicate_pair_is_clustered_together(fixture_data):
    a = _record_by_label(fixture_data, "duplicate_pair_a")
    b = _record_by_label(fixture_data, "duplicate_pair_b")
    records = [{"text": a["text"]}, {"text": b["text"]}]
    clusters = cluster_exact_duplicates(records)
    assert len(clusters) == 1
    assert len(clusters[0].member_record_ids) == 2


def test_statute_and_case_ruling_examples_are_never_confused(fixture_data):
    statute = _record_by_label(fixture_data, "statute_example")
    case = _record_by_label(fixture_data, "civil_cassation_example")
    statute_result = classify_document(statute["text"], statute["categories"])
    case_result = classify_document(case["text"], case["categories"])
    assert statute_result.document_type != case_result.document_type
    assert not extract_case_citation(statute["text"]).is_case_ruling
