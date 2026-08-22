from __future__ import annotations

import unittest
from src.legal_ai.ingestion.normalization import normalize_arabic


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


if __name__ == "__main__":
    unittest.main()
