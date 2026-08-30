"""article_segmentation.py — Deterministic Arabic legal article-boundary extraction.

Purpose: given a long law text (as expected from dataflare/egypt-legal-corpus,
where a single record can contain "substantial portions of complete laws"),
split it into (article_number, article_text) segments using explicit Arabic
legal article markers.

This is Stage 1's "Article/section structure extraction" step
(DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md processing plan) and the
direct technical foundation for H2 (article-aware chunking vs generic
chunking) — you cannot test H2 without first being able to find article
boundaries at all.

Honesty note (do not overstate): this is a v1 heuristic built and unit-tested
against synthetic fixtures modeled on the known "المادة N - ..." pattern
already observed in the existing 952-article corpus's `embedding_text` field
and scripts/build_eval_set.py's stripping regex. It has NOT been validated
against real Dataflare text, because that text is not yet accessible in this
environment (see docs/research/STAGE_1_REPORT.md). Precision/recall against the real
corpus must be measured at first real ingestion, not assumed from this file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.legal_ai.ingestion.normalization import nfc_normalize

# Arabic-Indic and Western digit article markers, plus common spelled-out
# ordinal forms used in Egyptian legal text for low article numbers.
_DIGIT = r"[0-9\u0660-\u0669]+"
_ORDINAL_WORDS_RAW = (
    "الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة",
    "السادسة", "السابعة", "الثامنة", "التاسعة", "العاشرة",
)
_ORDINAL_WORDS = "|".join(nfc_normalize(w) for w in _ORDINAL_WORDS_RAW)

# Words that, immediately before "مادة"/"المادة", indicate a REFERENCE to
# another article ("في المادة 5", "طبقا للمادة 10") rather than a genuine
# article-boundary marker introducing new article text. Excluded via
# negative lookbehind. Derived from real Dataflare corpus samples (see
# docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md, "Full corpus
# archaeology" — this list is not exhaustive; a v1 heuristic, not a
# validated parser).
_REFERENCE_PREFIXES = (
    r"في|فى|من|الى|إلى|على|عن|حكم|لحكم|احكام|لاحكام|بحكم|بموجب|طبقا|"
    r"طبقاً|وفق|وفقا|وفقاً|نص|بنص|لنص|هذه|تلك|بهذه|لهذه|بتلك|لتلك"
)

# v2: matches "مادة N" / "المادة N" ANYWHERE in continuous text (no newline
# required), which is what real Dataflare records need. Matches immediately
# preceded by a referential preposition/word (see _REFERENCE_PREFIXES) are
# filtered out in a post-match step (word-boundary lookbehind can't express
# a variable-length word list directly) so "طبقا للمادة 5" (a reference) is
# not mistaken for article 5's boundary.
_ARTICLE_MARKER_INLINE_RE = re.compile(
    rf"(?:مادة|المادة)\s*"
    rf"(?P<num>{_DIGIT}(?:\s*(?:مكرر|مكررا)(?:\s*{_DIGIT})?)?|{_ORDINAL_WORDS})"
    rf"\s*[-:.]?\s*",
)
_REFERENCE_PREFIX_WORDS = frozenset(_REFERENCE_PREFIXES.split("|"))


def _preceded_by_reference_word(text: str, match_start: int) -> bool:
    """True if the match at `match_start` is a referential mention of
    another article rather than a boundary marker — either because a
    referential word precedes it as a separate token ("في مادة 5"), or
    because a preposition is fused directly onto the marker word with no
    space ("للمادة 5" = لل + مادة, one token)."""
    # Fused-prefix case: check characters immediately before match_start
    # (no whitespace) against attached-preposition forms that unambiguously
    # indicate a reference ("للمادة" = لل + مادة = "to/according to the
    # article"). Deliberately excludes single-letter fused conjunctions
    # (و/ف/ل/ب) since those are far too common before a genuine new article
    # too (e.g. "والمادة 5 تنص على..." legitimately introduces article 5).
    for fused_prefix in ("بال", "لل"):
        if text[max(0, match_start - len(fused_prefix)) : match_start] == fused_prefix:
            # Only treat as fused-reference if what precedes THAT is a
            # word boundary (start of text or whitespace/punctuation).
            before_prefix = text[: match_start - len(fused_prefix)]
            if not before_prefix or before_prefix[-1] in " \n\t.:،,[]()":
                return True

    # Standalone-word case: last whitespace-delimited token before the match.
    before = text[:match_start].rstrip()
    if not before:
        return False
    last_word = before.split()[-1].strip(".:،,[]()")
    return last_word in _REFERENCE_PREFIX_WORDS


@dataclass
class ArticleSegment:
    article_number_raw: str  # exactly as matched (e.g. "42", "42 مكرر", "الأولى")
    text: str
    start_offset: int
    end_offset: int
    order_index: int


@dataclass
class SegmentationResult:
    segments: list[ArticleSegment] = field(default_factory=list)
    unmatched_prefix: str = ""  # any text before the first recognized marker
    marker_count: int = 0
    coverage_ratio: float = 0.0  # fraction of input text captured in segments
    strategy: str = "none"  # "line_start" | "inline" | "none"

    def to_dict(self) -> dict:
        return {
            "segment_count": len(self.segments),
            "marker_count": self.marker_count,
            "coverage_ratio": self.coverage_ratio,
            "strategy": self.strategy,
            "has_unmatched_prefix": bool(self.unmatched_prefix.strip()),
            "segments": [
                {
                    "article_number_raw": s.article_number_raw,
                    "text_preview": s.text[:80],
                    "text_length": len(s.text),
                    "order_index": s.order_index,
                }
                for s in self.segments
            ],
        }


def segment_articles(law_text: str) -> SegmentationResult:
    """Split a long law text into article segments at explicit markers.

    Deterministic, single-pass, no model calls. Matches "مادة N"/"المادة N"
    anywhere in the text — not just at line starts — because real Dataflare
    records are a single continuous flattened paragraph with no internal
    newlines (confirmed by full-corpus archaeology). Matches immediately
    preceded by a referential word (see _REFERENCE_PREFIXES) are excluded
    so "طبقا للمادة 5" (a reference to article 5) is not double-counted as
    a second boundary for article 5.

    If no markers are found, the result has zero segments and the entire
    text as `unmatched_prefix` — the caller must treat that as "structure
    not detected", not "law has one article", per the "do not guess" rule.
    This is the correct outcome for records with no article structure at
    all (petition templates, explanatory prose — confirmed present in the
    real corpus), not a parser failure.
    """
    if not law_text or not law_text.strip():
        return SegmentationResult()

    # NFC normalization first: real Egyptian legal corpora have been
    # observed to use decomposed hamza forms inconsistently (confirmed on
    # dataflare/egypt-legal-corpus — see DR-024), which would otherwise
    # silently break matching against hamza-bearing markers like "الأولى".
    # Offsets below refer to positions in this NFC-normalized text, which
    # is very close to but not always byte-identical to the raw source
    # (decomposed multi-codepoint sequences become single precomposed
    # characters) — a documented limitation, not a silent one.
    law_text = nfc_normalize(law_text)

    raw_matches = list(_ARTICLE_MARKER_INLINE_RE.finditer(law_text))
    matches = [m for m in raw_matches if not _preceded_by_reference_word(law_text, m.start())]

    if not matches:
        return SegmentationResult(unmatched_prefix=law_text, marker_count=0)

    result = SegmentationResult(unmatched_prefix=law_text[: matches[0].start()].strip())
    result.marker_count = len(matches)
    result.strategy = "inline"

    captured_chars = 0
    for i, m in enumerate(matches):
        text_start = m.end()
        text_end = matches[i + 1].start() if i + 1 < len(matches) else len(law_text)
        segment_text = law_text[text_start:text_end].strip()
        result.segments.append(
            ArticleSegment(
                article_number_raw=m.group("num").strip(),
                text=segment_text,
                start_offset=text_start,
                end_offset=text_end,
                order_index=i,
            )
        )
        captured_chars += len(segment_text)

    result.coverage_ratio = captured_chars / len(law_text) if law_text else 0.0
    return result


__all__ = ["ArticleSegment", "SegmentationResult", "segment_articles"]
