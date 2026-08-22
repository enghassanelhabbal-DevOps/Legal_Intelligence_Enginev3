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


def tokenize(text: str) -> list[str]:
    """Tokenize normalized Arabic text into whitespace-separated tokens."""
    return normalize_arabic(text).split()


__all__ = ["normalize_arabic", "tokenize"]
