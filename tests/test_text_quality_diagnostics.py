from __future__ import annotations

from src.legal_ai.ingestion.text_quality_diagnostics import (
    detect_probable_extraction_noise_prefix,
    scan_corpus_for_noise_prefix,
)

# These are the *actual* opening fragments observed in the real Dataflare
# viewer sample (docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md).
_REAL_OBSERVED_NOISY_SAMPLES = [
    "دودو 10 قانون الاجراءات الجنائية طبقا لاحدث التعديلات",
    "دودو 4 قانون المحاماة والادارات القانونية وفق احدث التعديلات",
    "دودو 3 قانون الاثبـات في المواد المدنية والتجارية",
    "دودو 5 امر خروج نهائي مجموعة",
    "048 بونو 1 وين 1 المواعيد والمدد القانونية في القـانون ال",
]

_REAL_OBSERVED_CLEAN_SAMPLES = [
    "قانون المرافعات احكام عامة مادة 1 تسرى قوانين المرافعات",
    "رئيس الجمهورية قر مجلس الشعب القانون الاتي نصه",
    "القرارات الوزارية الخاصة بالجمارك م رقم القرار",
]


def test_real_observed_noisy_samples_are_flagged():
    for text in _REAL_OBSERVED_NOISY_SAMPLES:
        flag = detect_probable_extraction_noise_prefix(text)
        assert flag.is_suspected, f"expected flag for: {text!r}"


def test_real_observed_clean_samples_not_flagged():
    for text in _REAL_OBSERVED_CLEAN_SAMPLES:
        flag = detect_probable_extraction_noise_prefix(text)
        assert not flag.is_suspected, f"unexpected flag for: {text!r}"


def test_matched_token_and_number_extracted():
    flag = detect_probable_extraction_noise_prefix("دودو 10 قانون الاجراءات الجنائية")
    assert flag.matched_token == "دودو"
    assert flag.matched_number == "10"


def test_empty_text_not_flagged():
    flag = detect_probable_extraction_noise_prefix("")
    assert not flag.is_suspected


def test_our_existing_952_corpus_sample_not_flagged():
    """Regression guard: the diagnostic must not false-positive on the
    existing, already-clean 952-article corpus text style."""
    text = "تسرى أحكام هذا القانون على كل من يرتكب في القطر المصري جريمة"
    flag = detect_probable_extraction_noise_prefix(text)
    assert not flag.is_suspected


def test_scan_corpus_reports_ratio_and_examples():
    records = [
        {"document_id": "1", "raw_text": _REAL_OBSERVED_NOISY_SAMPLES[0]},
        {"document_id": "2", "raw_text": _REAL_OBSERVED_CLEAN_SAMPLES[0]},
        {"document_id": "3", "raw_text": _REAL_OBSERVED_NOISY_SAMPLES[1]},
    ]
    report = scan_corpus_for_noise_prefix(records)
    assert report.records_checked == 3
    assert report.suspected_count == 2
    assert abs(report.suspected_ratio - (2 / 3)) < 1e-9
    assert len(report.examples) == 2


def test_scan_corpus_does_not_mutate_input():
    records = [{"document_id": "1", "raw_text": _REAL_OBSERVED_NOISY_SAMPLES[0]}]
    original = records[0]["raw_text"]
    scan_corpus_for_noise_prefix(records)
    assert records[0]["raw_text"] == original
