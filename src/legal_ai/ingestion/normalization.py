"""normalization.py — Arabic text normalization utilities.

Migrated from legal_ai/normalization.py.
Rule: normalization must be configurable and reversible for preserving exact legal text
(ARCHITECTURE_CONTRACT.md §Constraints).
"""

from __future__ import annotations

import re
import unicodedata

# Characters outside Arabic range + word chars are collapsed to a space
_ARABIC_RE = re.compile(r"[^\w\u0600-\u06FF]+", flags=re.UNICODE)


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for retrieval (NOT for display — the original is preserved).

    Steps applied in order:
      1. NFKC Unicode normalization
      2. Lowercase
      3. Remove tatweel (ـ)
      4. Normalize alef variants (إأآٱ) → ا
      5. Normalize final ya (ى) → ي
      6. Remove diacritics (tashkeel, shadda, etc.)
      7. Replace non-Arabic / non-word chars with space
      8. Collapse whitespace
    """
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = text.replace("ـ", "")                           # remove tatweel
    text = re.sub("[إأآٱ]", "ا", text)                    # normalize alef
    text = text.replace("ى", "ي")                         # normalize final ya
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)     # remove diacritics
    text = _ARABIC_RE.sub(" ", text)
    return " ".join(text.split())


def nfc_normalize(text: str) -> str:
    """NFC-only normalization — composes decomposed combining marks (e.g.
    ALEF+YEH+COMBINING-HAMZA-ABOVE into precomposed ئ) WITHOUT the
    aggressive rewriting normalize_arabic() does (no lowercasing, no alef
    merging, no diacritic stripping, no tatweel removal).

    Use this before substring/regex matching of hardcoded Arabic marker
    strings (document type classification, article segmentation, citation
    extraction, text-quality diagnostics) — real Egyptian legal corpora
    have been observed to use decomposed hamza forms inconsistently
    (confirmed on dataflare/egypt-legal-corpus: a hand-typed precomposed
    marker like "نقض جنائي" silently failed to match real category text
    using the decomposed form, with zero visible difference when printed).
    NFC preserves the character count/meaning closely enough that
    offset-based operations (e.g. article_segmentation's start/end
    offsets) remain meaningful, unlike normalize_arabic()'s more
    aggressive rewriting.
    """
    return unicodedata.normalize("NFC", str(text))


def tokenize(text: str) -> list[str]:
    """Tokenize normalized Arabic text into whitespace-separated tokens."""
    return normalize_arabic(text).split()


__all__ = ["normalize_arabic", "nfc_normalize", "tokenize"]
