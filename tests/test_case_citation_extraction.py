from __future__ import annotations

from src.legal_ai.ingestion.case_citation_extraction import extract_case_citation

# Real citation format observed in the corpus (see docs/DATASET_ASSESSMENT...)
_REAL_CITATION_TEXT = (
    "المنع من سماع الدعوى الطعن رقم 0003 لسنة 46 مكتب فنى 27 صفحة رقم "
    "1851 بتاريخ 29-12-1976 الموضوع : احوال شخصية لغير المسلمين الموضوع "
    "الفرعي : المنع من سماع الدعوى فقرة رقم 1"
)


def test_statute_text_is_not_flagged_as_case_ruling():
    text = "المادة 1 - تسرى أحكام هذا القانون على كل من يرتكب جريمة."
    citation = extract_case_citation(text)
    assert citation.is_case_ruling is False
    assert citation.citation_key() is None


def test_real_case_citation_extracted_correctly():
    citation = extract_case_citation(_REAL_CITATION_TEXT)
    assert citation.is_case_ruling is True
    assert citation.appeal_no == "0003"
    assert citation.year == "46"
    assert citation.technical_office == "27"
    assert citation.page == "1851"
    assert citation.date == "29-12-1976"


def test_citation_key_is_stable_and_human_readable():
    citation = extract_case_citation(_REAL_CITATION_TEXT)
    key = citation.citation_key()
    assert key is not None
    assert "0003" in key
    assert "46" in key


def test_citation_key_none_when_extraction_incomplete():
    text = "الطعن رقم فقط بدون باقي التفاصيل مكتب فنى"
    citation = extract_case_citation(text)
    assert citation.is_case_ruling is True
    assert citation.citation_key() is None


def test_empty_text_not_flagged_as_case_ruling():
    citation = extract_case_citation("")
    assert citation.is_case_ruling is False


def test_two_case_rulings_with_different_appeal_numbers_get_different_keys():
    text_a = "الطعن رقم 0001 لسنة 40 مكتب فنى 10 صفحة رقم 5 بتاريخ 01-01-1970"
    text_b = "الطعن رقم 0002 لسنة 41 مكتب فنى 11 صفحة رقم 6 بتاريخ 02-02-1971"
    key_a = extract_case_citation(text_a).citation_key()
    key_b = extract_case_citation(text_b).citation_key()
    assert key_a != key_b
