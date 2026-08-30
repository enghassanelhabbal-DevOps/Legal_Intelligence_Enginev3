"""text_quality_diagnostics.py — Detects, but does not silently fix, probable
source-extraction noise in legal text records.

This module exists because of a real observation, not a hypothesis: fetching
10 real rows from the dataflare/egypt-legal-corpus public viewer (see
docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md, "Real sample
findings") showed several unrelated laws' `text` fields opening with short,
meaningless tokens before the actual legal content starts, e.g.:

    "دودو 10 قانون الاجراءات الجنائية طبقا لاحدث التعديلات..."
    "دودو 4 قانون المحاماة والادارات القانونية..."
    "048 بونو 1 وين 1 المواعيد والمدد القانونية..."

The repeated "دودو <small number>" pattern across otherwise-unrelated laws is
consistent with a systematic PDF/OCR extraction artifact (e.g. a
watermark, page-number stamp, or scanner signature misread as Arabic text),
not meaningful legal content. This is a pattern-level observation from a
10-row sample — not confirmed against the full 2,434-row corpus.

Per governance (do not guess, do not silently fix data): this module FLAGS
suspected noise for manifest/report visibility. It does not strip or alter
any text. A future ingestion-cleaning decision must be made explicitly (its
own DR), with the full corpus available to validate the pattern's true
extent, false-positive rate, and the correct removal boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.legal_ai.ingestion.normalization import nfc_normalize

# Observed pattern A: 1-2 short Arabic tokens (not full legal-opening
# phrases) immediately followed by a small integer, at the very start of the
# text, before any recognizable legal-document opening phrase.
# e.g. "دودو 10 قانون الاجراءات الجنائية..."
_SUSPECT_PREFIX_RE = re.compile(
    r"^\s*(?P<token>[\u0600-\u06FF]{2,6})\s+(?P<num>[0-9\u0660-\u0669]{1,3})\b"
)

# Observed pattern B: a leading small integer followed by 1-2 short tokens,
# with a second integer nearby — a messier variant of the same artifact class.
# e.g. "048 بونو 1 وين 1 المواعيد والمدد القانونية..."
# This is a broader, lower-precision pattern than A and is more likely to
# false-positive; kept separate so callers can distinguish confidence if
# needed later (not yet exposed — v1 treats both as "suspected").
_SUSPECT_PREFIX_DIGIT_FIRST_RE = re.compile(
    r"^\s*(?P<num>[0-9\u0660-\u0669]{1,4})\s+(?P<token>[\u0600-\u06FF]{2,6})\s+"
    r"[0-9\u0660-\u0669]{1,3}\b"
)

# Legal-document opening phrases that indicate the text starts cleanly
# (observed in the existing 952-corpus and in clean Dataflare rows).
_CLEAN_OPENING_MARKERS = tuple(
    nfc_normalize(m)
    for m in ("قانون", "المادة", "مادة", "رئيس الجمهورية", "قرار", "باسم الشعب")
)


@dataclass
class NoisePrefixFlag:
    is_suspected: bool
    matched_token: str | None = None
    matched_number: str | None = None
    prefix_preview: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "is_suspected": self.is_suspected,
            "matched_token": self.matched_token,
            "matched_number": self.matched_number,
            "prefix_preview": self.prefix_preview,
            "reason": self.reason,
        }


def detect_probable_extraction_noise_prefix(text: str, preview_chars: int = 40) -> NoisePrefixFlag:
    """Flag (never strip) text whose opening matches the observed
    '<short token> <small number>' extraction-noise pattern rather than a
    recognizable legal-document opening.
    """
    if not text or not text.strip():
        return NoisePrefixFlag(is_suspected=False, reason="empty text")

    text = nfc_normalize(text)
    stripped = text.lstrip()
    starts_clean = any(stripped.startswith(marker) for marker in _CLEAN_OPENING_MARKERS)
    if starts_clean:
        return NoisePrefixFlag(is_suspected=False, reason="starts with a recognized legal opening")

    match = _SUSPECT_PREFIX_RE.match(stripped)
    pattern_name = "token_then_number"
    if not match:
        match = _SUSPECT_PREFIX_DIGIT_FIRST_RE.match(stripped)
        pattern_name = "digit_then_token"
    if not match:
        return NoisePrefixFlag(is_suspected=False, reason="no suspect prefix pattern found")

    return NoisePrefixFlag(
        is_suspected=True,
        matched_token=match.group("token"),
        matched_number=match.group("num"),
        prefix_preview=stripped[:preview_chars],
        reason=(
            f"text opens with a suspected extraction-noise pattern ({pattern_name}) "
            "before any recognized legal-document opening phrase; consistent with an "
            "OCR/extraction artifact observed in a real Dataflare sample, "
            "unconfirmed at scale — this is a v1 heuristic covering 2 observed "
            "variants from a 10-row sample, not a validated corpus-wide rule"
        ),
    )


@dataclass
class CorpusNoiseReport:
    records_checked: int = 0
    suspected_count: int = 0
    suspected_ratio: float = 0.0
    examples: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "records_checked": self.records_checked,
            "suspected_count": self.suspected_count,
            "suspected_ratio": self.suspected_ratio,
            "examples": self.examples,
        }


def scan_corpus_for_noise_prefix(
    records: list[dict], text_field: str = "raw_text", max_examples: int = 10
) -> CorpusNoiseReport:
    """Bounded, single-pass scan of a record list for the suspected noise
    pattern. Read-only diagnostic — does not modify `records`."""
    report = CorpusNoiseReport(records_checked=len(records))
    for rec in records:
        text = str(rec.get(text_field, "") or "")
        flag = detect_probable_extraction_noise_prefix(text)
        if flag.is_suspected:
            report.suspected_count += 1
            if len(report.examples) < max_examples:
                report.examples.append(
                    {"document_id": rec.get("document_id"), **flag.to_dict()}
                )
    report.suspected_ratio = (
        report.suspected_count / report.records_checked if report.records_checked else 0.0
    )
    return report


__all__ = [
    "NoisePrefixFlag",
    "CorpusNoiseReport",
    "detect_probable_extraction_noise_prefix",
    "scan_corpus_for_noise_prefix",
]
