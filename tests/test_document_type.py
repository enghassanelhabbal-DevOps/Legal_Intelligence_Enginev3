from __future__ import annotations

from src.legal_ai.domain.document_type import DocumentType, classify_document


def _decomposed(base: str, combining_codepoint: int, insert_after_index: int) -> str:
    """Build a string with a DECOMPOSED combining mark inserted after the
    character at insert_after_index — e.g. turning precomposed 'ئ' usage
    into ALEF+YEH+COMBINING-HAMZA-ABOVE, matching what was found in the
    real corpus (see DR-024). Built programmatically, not hand-typed, so
    this test cannot silently suffer the same typing-artifact bug that
    caused the original miss."""
    chars = list(base)
    chars.insert(insert_after_index + 1, chr(combining_codepoint))
    return "".join(chars)


def test_empty_text_is_invalid():
    result = classify_document("")
    assert result.document_type == DocumentType.INVALID
    assert result.confidence == 1.0


def test_statute_text_classified_as_statute():
    result = classify_document("قانون رقم 95 لسنة 2003 المادة 1 تسرى احكام هذا القانون")
    assert result.document_type == DocumentType.STATUTE


def test_civil_cassation_classified_correctly():
    text = "الطعن رقم 0003 لسنة 46 مكتب فنى 27 صفحة رقم 1851"
    result = classify_document(text, categories=["نقض مدني جزء اول"])
    assert result.document_type == DocumentType.JUDICIAL_CASSATION_CIVIL
    assert result.confidence > 0.5


def test_criminal_cassation_classified_correctly():
    text = "الطعن رقم 0010 لسنة 50 مكتب فنى 15 صفحة رقم 200"
    result = classify_document(text, categories=["نقض جنائي جزء الاول"])
    assert result.document_type == DocumentType.JUDICIAL_CASSATION_CRIMINAL


def test_administrative_classified_correctly():
    text = "الطعن رقم 0005 لسنة 55 مكتب فنى 8 صفحة رقم 90"
    result = classify_document(text, categories=["اداريا عليا جزء اول"])
    assert result.document_type == DocumentType.JUDICIAL_ADMINISTRATIVE


def test_combined_tag_alone_is_ambiguous_not_forced():
    """Real corpus finding: a record with ONLY the combined
    'النقض و المحكمة الادارية' tag and no specific sub-tag must not be
    forced into civil/criminal/administrative."""
    text = "الطعن رقم 0001 لسنة 40 مكتب فنى 5 صفحة رقم 10"
    result = classify_document(text, categories=["النقض و المحكمة الادارية"])
    assert result.document_type == DocumentType.JUDICIAL_OTHER


def test_specific_subtype_wins_even_with_combined_tag_present():
    """Real corpus finding: categories are hierarchical — a specific
    sub-tag (نقض مدني) normally co-occurs WITH the combined parent tag on
    the same record. The specific tag must still win."""
    text = "الطعن رقم 0002 لسنة 41 مكتب فنى 6 صفحة رقم 20"
    result = classify_document(
        text, categories=["النقض و المحكمة الادارية", "نقض مدني جزء اول"]
    )
    assert result.document_type == DocumentType.JUDICIAL_CASSATION_CIVIL


def test_administrative_marker_does_not_false_positive_on_combined_tag():
    """Regression for the real substring-collision bug found during
    validation: 'المحكمة الادارية' is a literal substring of the combined
    tag 'النقض و المحكمة الادارية', which previously caused every
    combined-tag record to be wrongly classified as pure administrative."""
    text = "الطعن رقم 0009 لسنة 44 مكتب فنى 3 صفحة رقم 7"
    result = classify_document(text, categories=["النقض و المحكمة الادارية"])
    assert result.document_type != DocumentType.JUDICIAL_ADMINISTRATIVE


def test_legal_form_template_classified_correctly():
    text = "انه فى يوم الموافق / / بناء على طلب السيد المقيم بشارع كذا"
    result = classify_document(text)
    assert result.document_type == DocumentType.LEGAL_FORM


def test_no_signal_matched_is_unknown_not_guessed():
    text = "نص عربي عام بدون اي اشارة الى نوع مستند قانوني محدد على الاطلاق"
    result = classify_document(text)
    assert result.document_type == DocumentType.UNKNOWN
    assert result.confidence == 0.0


def test_human_override_wins_over_classifier_result():
    result = classify_document("قانون رقم 1 المادة 1")
    result.human_override = DocumentType.REGULATION
    assert result.effective_type == DocumentType.REGULATION
    assert result.document_type == DocumentType.STATUTE  # original preserved


# --- decomposed-hamza regression (built programmatically, not hand-typed) --


def test_criminal_cassation_matches_with_decomposed_hamza_in_category():
    """Regression for DR-024: real Dataflare category text used a
    decomposed combining-hamza sequence (ALEF+YEH+COMBINING-HAMZA-ABOVE)
    where a precomposed 'ئ' would normally appear, and a hand-typed
    precomposed marker silently failed to match it. This test constructs
    the decomposed form programmatically so it cannot fall into the same
    typing-artifact trap the original bug came from."""
    base_precomposed = "نقض جنائي جزء الاول"  # contains 'ئ' (U+0626) at index 7
    # Rebuild with the decomposed form: replace 'ئ' with يّ + combining hamza above
    decomposed = base_precomposed.replace("ئ", "ي" + chr(0x654))
    assert decomposed != base_precomposed  # sanity: actually different bytes

    text = "الطعن رقم 0004 لسنة 42 مكتب فنى 9 صفحة رقم 15"
    result = classify_document(text, categories=[decomposed])
    assert result.document_type == DocumentType.JUDICIAL_CASSATION_CRIMINAL


def test_document_type_result_to_dict_shape():
    result = classify_document("قانون رقم 1 المادة 1")
    d = result.to_dict()
    assert set(d.keys()) == {
        "document_type",
        "effective_type",
        "confidence",
        "signals",
        "classifier_version",
        "human_override",
    }
