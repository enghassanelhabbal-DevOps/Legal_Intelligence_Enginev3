"""document_type.py — canonical legal-resource document-type classification.

Per docs/research/CORPUS_ARCHITECTURE_DIRECTION.md and the corpus archaeology
findings (docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md): the
corpus is heterogeneous (legislation, Court of Cassation, administrative
judiciary, forms, commentary, academic material). A single flat
statute-vs-case-ruling boolean is not enough — this module replaces that
with a controlled classification carrying confidence, reasons, and a
distinct UNKNOWN state that must not be silently forced into a guess.

Confidence explicitly does NOT imply legal authority — see
LegalResourceIdentity.provenance_status for that separate concern. A
classifier being 0.95 confident this is JUDICIAL_CASSATION_CIVIL says
nothing about whether the underlying text is a verified primary source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from src.legal_ai.ingestion.normalization import nfc_normalize

CLASSIFIER_VERSION = "rule_based_v1"


class DocumentType(StrEnum):
    STATUTE = "statute"
    REGULATION = "regulation"
    CONSTITUTIONAL_MATERIAL = "constitutional_material"
    JUDICIAL_CASSATION_CIVIL = "judicial_cassation_civil"
    JUDICIAL_CASSATION_CRIMINAL = "judicial_cassation_criminal"
    JUDICIAL_ADMINISTRATIVE = "judicial_administrative"
    JUDICIAL_OTHER = "judicial_other"
    INTERNATIONAL_INSTRUMENT = "international_instrument"
    LEGAL_FORM = "legal_form"
    COMMENTARY = "commentary"
    ACADEMIC = "academic"
    MIXED = "mixed"
    UNKNOWN = "unknown"
    INVALID = "invalid"


@dataclass
class DocumentTypeResult:
    document_type: DocumentType
    confidence: float  # 0.0-1.0; a rule-based heuristic strength, not a probability
    signals: list[str] = field(default_factory=list)  # human-readable reasons
    classifier_version: str = CLASSIFIER_VERSION
    human_override: DocumentType | None = None

    @property
    def effective_type(self) -> DocumentType:
        """The type to actually use downstream: a human override always wins."""
        return self.human_override if self.human_override is not None else self.document_type

    def to_dict(self) -> dict:
        return {
            "document_type": self.document_type.value,
            "effective_type": self.effective_type.value,
            "confidence": self.confidence,
            "signals": self.signals,
            "classifier_version": self.classifier_version,
            "human_override": self.human_override.value if self.human_override else None,
        }


# --- rule-based classification signals -------------------------------

_CASSATION_CIVIL_MARKERS = tuple(nfc_normalize(m) for m in ("نقض مدني", "نقض مدنى"))
_CASSATION_CRIMINAL_MARKERS = tuple(nfc_normalize(m) for m in ("نقض جنائي", "نقض جنائى"))
# Deliberately excludes the generic "المحكمة الادارية" — that phrase is a
# literal substring of the COMBINED category tag "النقض و المحكمة الادارية"
# (cassation-and-administrative-court, a genuinely mixed bucket), so
# matching it would wrongly label combined-tag records as pure
# administrative. Caught during real-corpus validation (2,051 records
# carry that combined tag) — kept narrow to Supreme-Administrative-specific
# markers only.
_ADMINISTRATIVE_MARKERS = tuple(
    nfc_normalize(m) for m in ("اداريا عليا", "إداريا عليا", "الادارية العليا")
)
_COMBINED_JUDICIAL_MARKER = nfc_normalize("النقض و المحكمة الادارية")
_CASE_CITATION_MARKERS = tuple(nfc_normalize(m) for m in ("الطعن رقم", "مكتب فنى", "مكتب فني"))
_STATUTE_MARKERS = tuple(nfc_normalize(m) for m in ("قانون رقم", "المادة", "مادة "))
_FORM_MARKERS = tuple(
    nfc_normalize(m)
    for m in (
        "انه فى يوم الموافق",
        "انه في يوم الموافق",
        "بناء على طلب السيد",
        "بناء على طلب السيدة",
    )
)
_CONSTITUTIONAL_MARKERS = tuple(nfc_normalize(m) for m in ("الدستور", "المحكمة الدستورية"))
_INTERNATIONAL_MARKERS = tuple(
    nfc_normalize(m) for m in ("الاتفاقية الدولية", "اتفاقية دولية", "المعاهدة")
)


def classify_document(
    text: str,
    categories: list[str] | None = None,
) -> DocumentTypeResult:
    """Deterministic, rule-based classification. No model calls.

    This is intentionally a rule-based baseline (per the master prompt's
    "measurement first" / "do not train a classifier unless a rule-based
    baseline proves inadequate" instruction) — its unknown/low-confidence
    rate is itself a metric to report, not a thing to hide by forcing a
    guess.
    """
    categories = categories or []
    text = nfc_normalize(text) if text else text
    cat_text = nfc_normalize(" ".join(categories))
    signals: list[str] = []

    if not text or not text.strip():
        return DocumentTypeResult(
            document_type=DocumentType.INVALID, confidence=1.0, signals=["empty_text"]
        )

    has_citation = any(m in text for m in _CASE_CITATION_MARKERS)
    is_civil_cassation = any(m in cat_text for m in _CASSATION_CIVIL_MARKERS)
    is_criminal_cassation = any(m in cat_text for m in _CASSATION_CRIMINAL_MARKERS)
    is_administrative = any(m in cat_text for m in _ADMINISTRATIVE_MARKERS)

    if has_citation:
        signals.append("case_citation_pattern_found")
        if is_civil_cassation and not is_criminal_cassation and not is_administrative:
            signals.append("category:civil_cassation")
            return DocumentTypeResult(DocumentType.JUDICIAL_CASSATION_CIVIL, 0.85, signals)
        if is_criminal_cassation and not is_civil_cassation and not is_administrative:
            signals.append("category:criminal_cassation")
            return DocumentTypeResult(DocumentType.JUDICIAL_CASSATION_CRIMINAL, 0.85, signals)
        if is_administrative and not is_civil_cassation and not is_criminal_cassation:
            signals.append("category:administrative")
            return DocumentTypeResult(DocumentType.JUDICIAL_ADMINISTRATIVE, 0.85, signals)
        # No single specific sub-type marker matched cleanly. Categories are
        # hierarchical (a broad "النقض و المحكمة الادارية" tag typically
        # co-occurs with a specific "نقض مدني"/"نقض جنائي"/"اداريا عليا"
        # child tag on the same record — confirmed by real-corpus counts:
        # 1293+415+343 = 2051 = the combined-tag count exactly). Reaching
        # here means either the combined tag alone is present with no
        # specific child tag, or multiple specific tags conflict — both are
        # genuinely ambiguous and must not be forced into a sub-type.
        if _COMBINED_JUDICIAL_MARKER in cat_text:
            signals.append("category:combined_tag_only_no_specific_subtype")
        else:
            signals.append("category_signal_ambiguous_or_absent")
        return DocumentTypeResult(DocumentType.JUDICIAL_OTHER, 0.55, signals)

    if any(m in text for m in _CONSTITUTIONAL_MARKERS):
        signals.append("constitutional_marker_found")
        return DocumentTypeResult(DocumentType.CONSTITUTIONAL_MATERIAL, 0.6, signals)

    if any(m in text for m in _INTERNATIONAL_MARKERS):
        signals.append("international_instrument_marker_found")
        return DocumentTypeResult(DocumentType.INTERNATIONAL_INSTRUMENT, 0.5, signals)

    if any(m in text[:200] for m in _FORM_MARKERS):
        signals.append("legal_form_template_marker_found")
        return DocumentTypeResult(DocumentType.LEGAL_FORM, 0.7, signals)

    if any(m in text for m in _STATUTE_MARKERS):
        signals.append("statute_marker_found")
        return DocumentTypeResult(DocumentType.STATUTE, 0.65, signals)

    signals.append("no_reliable_signal_matched")
    return DocumentTypeResult(DocumentType.UNKNOWN, 0.0, signals)


__all__ = ["DocumentType", "DocumentTypeResult", "classify_document", "CLASSIFIER_VERSION"]
