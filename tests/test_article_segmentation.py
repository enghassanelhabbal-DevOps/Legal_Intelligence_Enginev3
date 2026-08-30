from __future__ import annotations

from src.legal_ai.ingestion.article_segmentation import segment_articles


def test_basic_numbered_articles_split_correctly():
    text = "المادة 1 - نص أول.\n\nالمادة 2 - نص ثان."
    result = segment_articles(text)
    assert result.marker_count == 2
    assert [s.article_number_raw for s in result.segments] == ["1", "2"]
    assert "نص أول" in result.segments[0].text
    assert "نص ثان" in result.segments[1].text


def test_mokarrar_repeated_article_suffix_recognized():
    text = "المادة 5 - نص أساسي.\n\nالمادة 5 مكرر - نص إضافي بعد المادة الأصلية."
    result = segment_articles(text)
    assert result.marker_count == 2
    assert result.segments[1].article_number_raw == "5 مكرر"


def test_short_form_madda_without_al_prefix_recognized():
    text = "مادة 10 - نص تجريبي."
    result = segment_articles(text)
    assert result.marker_count == 1
    assert result.segments[0].article_number_raw == "10"


def test_ordinal_word_form_recognized():
    text = "المادة الأولى - نص باستخدام الترقيم اللفظي."
    result = segment_articles(text)
    assert result.marker_count == 1
    assert result.segments[0].article_number_raw == "الأولى"


def test_no_markers_found_reports_unmatched_not_a_guess():
    text = "نص عام بدون أي إشارة لمواد قانونية محددة."
    result = segment_articles(text)
    assert result.marker_count == 0
    assert result.segments == []
    assert result.unmatched_prefix == text


def test_empty_text_does_not_crash():
    result = segment_articles("")
    assert result.marker_count == 0
    assert result.segments == []


def test_text_before_first_marker_captured_as_unmatched_prefix():
    text = "عنوان القانون\n\nالمادة 1 - أول نص فعلي."
    result = segment_articles(text)
    assert "عنوان القانون" in result.unmatched_prefix
    assert result.marker_count == 1


def test_order_index_is_sequential():
    text = "المادة 1 - أ.\nالمادة 2 - ب.\nالمادة 3 - ج."
    result = segment_articles(text)
    assert [s.order_index for s in result.segments] == [0, 1, 2]


def test_coverage_ratio_between_zero_and_one():
    text = "مقدمة طويلة قبل النص.\n\nالمادة 1 - نص قصير."
    result = segment_articles(text)
    assert 0.0 <= result.coverage_ratio <= 1.0


def test_segmentation_is_deterministic():
    text = "المادة 1 - نص أ.\nالمادة 2 - نص ب."
    r1 = segment_articles(text)
    r2 = segment_articles(text)
    assert r1.to_dict() == r2.to_dict()


# --- inline (no-newline) real-corpus format ---------------------------
# Real dataflare/egypt-legal-corpus text is a single continuous paragraph
# with no internal newlines between articles (confirmed by full-corpus
# archaeology — see docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md).


def test_inline_continuous_text_without_newlines_is_segmented():
    text = (
        "قانون المرافعات احكام عامة مادة 1 تسرى قوانين المرافعات على ما لم "
        "يكن فصل فيه من الدعاوى . مادة 2 كل اجراء من الاجراءات يتم وفقا "
        "للقانون النافذ وقت اجرائه . مادة 3 لا يقبل اى طلب بعد الميعاد ."
    )
    result = segment_articles(text)
    assert result.strategy == "inline"
    assert result.marker_count == 3
    assert [s.article_number_raw for s in result.segments] == ["1", "2", "3"]


def test_line_start_strategy_preferred_when_newlines_present():
    text = "المادة 1 - نص أ.\nالمادة 2 - نص ب."
    result = segment_articles(text)
    assert result.strategy == "inline"
    assert result.marker_count == 2


def test_referential_mention_of_article_is_not_treated_as_boundary():
    """'طبقا للمادة 5' references article 5, it does not start it — must not
    be double-counted as a second boundary for the same article."""
    text = "مادة 5 نص الماده الاصلي . والحكم يطبق طبقا للمادة 5 في هذه الحالة . مادة 6 نص تال ."
    result = segment_articles(text)
    assert result.marker_count == 2
    assert [s.article_number_raw for s in result.segments] == ["5", "6"]


def test_reference_to_previous_article_with_various_prepositions_excluded():
    for prefix in ["في", "من", "طبقا", "وفقا", "لاحكام", "بموجب"]:
        text = f"مادة 1 نص اول . نص عام {prefix} مادة 1 يشير الى ما سبق . مادة 2 نص تال ."
        result = segment_articles(text)
        assert result.marker_count == 2, f"failed for prefix {prefix!r}: {result.marker_count}"


def test_real_corpus_template_document_correctly_reports_zero_markers():
    """A legal petition template (no article structure at all) must report
    zero markers, not force a false segmentation — real Dataflare sample."""
    text = (
        "دعوى بطلب الطلاق لخروج احد الزوجين عن الدين المسيحى وانقطاع الامل "
        "من رجوعه اليه انه فى يوم الموافق"
    )
    result = segment_articles(text)
    assert result.marker_count == 0
    assert result.strategy == "none"
    assert result.unmatched_prefix == text
