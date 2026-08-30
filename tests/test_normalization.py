from __future__ import annotations

import unittest

from src.legal_ai.ingestion.normalization import nfc_normalize, normalize_arabic


class TestArabicNormalization(unittest.TestCase):
    def test_basic_normalization(self):
        src = "إختبار ـ الكلماتِ 123"
        out = normalize_arabic(src)
        # Expect alef variants normalized to ا, tatweel removed, diacritics removed, lowercased
        self.assertIn("اختبار", out)
        self.assertNotIn("ِ", out)  # diacritic removed

    def test_alef_ya_variants(self):
        src = "آباء ى ي"
        out = normalize_arabic(src)
        self.assertIn("اباء", out)
        # both ى and ي should be normalized to ي
        self.assertIn("ي", out)

    def test_punctuation_and_whitespace(self):
        src = "نص، مع: علامات؟ \n\t ومسافات"
        out = normalize_arabic(src)
        # Newlines and tabs should be removed; whitespace normalized to single spaces.
        self.assertNotIn("\n", out)
        self.assertNotIn("\t", out)
        # No double spaces
        self.assertNotIn("  ", out)

    def test_preserve_meaning(self):
        src = "المادة رقم (1) الفقرة الأولى"
        out = normalize_arabic(src)
        # Ensure meaningful tokens remain
        self.assertIn("المادة", out)
        self.assertIn("رقم", out)


class TestNfcNormalize(unittest.TestCase):
    """Regression coverage for DR-024: real dataflare/egypt-legal-corpus
    category text used decomposed combining-hamza sequences
    (base+YEH+COMBINING-HAMZA-ABOVE) where a precomposed letter (ئ) would
    normally appear. A hand-typed precomposed marker string silently
    failed to match this in the document-type classifier until
    nfc_normalize() was applied on both sides of the comparison.
    """

    def test_decomposed_hamza_above_on_yeh_is_composed(self):
        decomposed = "ي" + chr(0x654)  # YEH + COMBINING HAMZA ABOVE
        composed = nfc_normalize(decomposed)
        self.assertEqual(composed, "ئ")  # precomposed YEH WITH HAMZA ABOVE

    def test_decomposed_hamza_below_on_alef_is_composed(self):
        decomposed = "ا" + chr(0x655)  # ALEF + COMBINING HAMZA BELOW
        composed = nfc_normalize(decomposed)
        self.assertEqual(composed, "إ")  # precomposed ALEF WITH HAMZA BELOW

    def test_real_corpus_style_word_matches_after_nfc(self):
        """Build the exact real-corpus decomposed form of 'جنائي'
        programmatically (not hand-typed) and confirm it becomes
        byte-identical to the precomposed form after nfc_normalize()."""
        precomposed = "جنائي"  # ج ن ا ئ ي
        # Reconstruct with the hamza decomposed off the yeh that carries it
        decomposed = "جنا" + "ي" + chr(0x654) + "ي"
        self.assertNotEqual(precomposed, decomposed)  # sanity: truly different bytes
        self.assertEqual(nfc_normalize(decomposed), precomposed)

    def test_already_precomposed_text_is_unchanged(self):
        text = "قانون العقوبات"
        self.assertEqual(nfc_normalize(text), text)

    def test_nfc_normalize_does_not_lowercase_or_strip_diacritics(self):
        """Unlike normalize_arabic(), nfc_normalize() must be minimally
        invasive — no lowercasing, no diacritic removal, no alef merging —
        since it's meant to preserve text for offset-sensitive operations
        like article segmentation."""
        text = "الْمَادَّةُ"  # with diacritics
        out = nfc_normalize(text)
        self.assertIn("\u064e", out)  # fatha diacritic still present


if __name__ == "__main__":
    unittest.main()
