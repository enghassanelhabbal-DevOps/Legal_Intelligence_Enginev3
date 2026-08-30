"""case_citation_extraction.py — Extracts Egyptian Court of Cassation (نقض)
citation structure from case-ruling records.

Full-corpus archaeology on the real dataflare/egypt-legal-corpus (see
docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md) found that 86.7%
of records (2,110 of 2,434) are case-ruling excerpts, not statute text —
identifiable by the citation pattern:

    "الطعن رقم <N> لسنة <Y> مكتب فنى <O> صفحة رقم <P> بتاريخ <DATE>"
    ("Appeal No. N of year Y, Technical Office O, page P, dated DATE")

This is the dominant document type in the corpus by record count, and each
citation is an independently verifiable precedent — exactly the kind of
citable evidence unit the project's groundedness goal (H4,
docs/research/RESEARCH_HYPOTHESES.md) needs. This module extracts that structure so
case rulings can be indexed and cited by their real court citation, not
just a generic content-derived id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.legal_ai.ingestion.normalization import nfc_normalize

_DIGIT = r"[0-9\u0660-\u0669]+"

_CITATION_RE = re.compile(
    rf"الطعن رقم\s*(?P<appeal_no>{_DIGIT})\s*لسنة\s*(?P<year>{_DIGIT})\s*"
    rf"مكتب فن[ىي]\s*(?P<office>{_DIGIT})\s*صفحة رقم\s*(?P<page>{_DIGIT})\s*"
    rf"بتاريخ\s*(?P<date>[\d\u0660-\u0669\-/]+)"
)

_SUBJECT_RE = re.compile(r"الموضوع\s*:\s*(?P<subject>[^:]+?)(?:الموضوع الفرعي|$)")
_SUBTOPIC_RE = re.compile(r"الموضوع الفرعي\s*:\s*(?P<subtopic>[^.]+?)(?:فقرة رقم|$)")


@dataclass
class CaseCitation:
    is_case_ruling: bool
    appeal_no: str | None = None
    year: str | None = None
    technical_office: str | None = None
    page: str | None = None
    date: str | None = None
    subject: str | None = None
    subtopic: str | None = None

    def to_dict(self) -> dict:
        return {
            "is_case_ruling": self.is_case_ruling,
            "appeal_no": self.appeal_no,
            "year": self.year,
            "technical_office": self.technical_office,
            "page": self.page,
            "date": self.date,
            "subject": self.subject,
            "subtopic": self.subtopic,
        }

    def citation_key(self) -> str | None:
        """A stable, human-readable citation identifier, suitable as a
        grouping key (leakage-safety) or a display citation. None if the
        citation could not be extracted."""
        if not (self.appeal_no and self.year and self.technical_office):
            return None
        return f"طعن:{self.appeal_no}/{self.year}:مكتب_فني:{self.technical_office}"


_CASE_PATTERN_RE = re.compile(r"الطعن رقم|مكتب فنى|مكتب فني")


def extract_case_citation(text: str) -> CaseCitation:
    """Detect whether `text` is a case-ruling excerpt and, if so, extract
    its citation structure. Returns is_case_ruling=False for statute text.

    Extraction is regex-based on the observed citation format; it may not
    match every case-ruling record (measured extraction coverage must be
    tracked per corpus, not assumed — see docs/DATASET_ASSESSMENT... for
    the coverage figure measured on this exact corpus)."""
    if not text:
        return CaseCitation(is_case_ruling=False)

    text = nfc_normalize(text)
    if not _CASE_PATTERN_RE.search(text):
        return CaseCitation(is_case_ruling=False)

    citation = CaseCitation(is_case_ruling=True)
    m = _CITATION_RE.search(text)
    if m:
        citation.appeal_no = m.group("appeal_no")
        citation.year = m.group("year")
        citation.technical_office = m.group("office")
        citation.page = m.group("page")
        citation.date = m.group("date")

    subj = _SUBJECT_RE.search(text)
    if subj:
        citation.subject = subj.group("subject").strip()
    subtopic = _SUBTOPIC_RE.search(text)
    if subtopic:
        citation.subtopic = subtopic.group("subtopic").strip()

    return citation


__all__ = ["CaseCitation", "extract_case_citation"]
