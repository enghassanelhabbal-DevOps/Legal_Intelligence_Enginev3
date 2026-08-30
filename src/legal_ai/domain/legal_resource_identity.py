"""legal_resource_identity.py — canonical legal-resource identity fields.

Per the master prompt: "Dataflare category ≠ legal authority" and
"law_name ≠ canonical legal identity" (the dataset card states law_name is
derived from source filenames). This module keeps the dataset's own label
as `source_law_name`/`source_topic_label` — never presented as a verified
canonical legal title — separate from canonical identity fields, which
start UNKNOWN until independently verified.

Two identity shapes, not nine inheritance classes (per the master prompt's
own "prefer simple, strongly typed, extensible design" instruction):
legislative and judicial. A shared UNKNOWN sentinel matches the pattern
already established in dataset_manifest.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

UNKNOWN = "unknown"


class ProvenanceStatus(StrEnum):
    """Source confidence — never inferred from how "legal-looking" text is."""

    VERIFIED_PRIMARY = "verified_primary"
    VERIFIED_SECONDARY = "verified_secondary"
    DATASET_DERIVED = "dataset_derived"
    UNVERIFIED = "unverified"
    UNKNOWN = UNKNOWN


@dataclass
class LegislativeIdentity:
    """Canonical identity for legislation/regulation/constitutional material.
    All fields start unknown; nothing here is inferred from dataset labels."""

    jurisdiction: str = UNKNOWN
    country: str = UNKNOWN
    instrument_type: str = UNKNOWN  # e.g. "law", "regulation", "decree"
    instrument_number: str | None = None
    instrument_year: str | None = None
    canonical_title: str = UNKNOWN
    issuing_authority: str = UNKNOWN
    effective_from: str | None = None
    effective_to: str | None = None
    status: str = UNKNOWN  # e.g. "in_force", "repealed", unknown
    version_id: str | None = None

    # Source label, explicitly NOT canonical identity (dataset card states
    # law_name is derived from source filenames, not verified titles).
    source_law_name: str = UNKNOWN

    def to_dict(self) -> dict:
        return {
            "resource_family": "legislative",
            "jurisdiction": self.jurisdiction,
            "country": self.country,
            "instrument_type": self.instrument_type,
            "instrument_number": self.instrument_number,
            "instrument_year": self.instrument_year,
            "canonical_title": self.canonical_title,
            "issuing_authority": self.issuing_authority,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "status": self.status,
            "version_id": self.version_id,
            "source_law_name": self.source_law_name,
        }


@dataclass
class JudicialIdentity:
    """Canonical identity for judicial/case-law material."""

    jurisdiction: str = UNKNOWN
    judicial_system: str = UNKNOWN  # e.g. "ordinary", "administrative", "constitutional"
    court: str = UNKNOWN
    court_level: str = UNKNOWN
    chamber: str | None = None
    case_type: str = UNKNOWN
    appeal_number: str | None = None
    judicial_year: str | None = None
    decision_date: str | None = None
    technical_office: str | None = None
    page: str | None = None
    citation: str | None = None  # stable citation_key, when extractable

    # Source label, explicitly NOT canonical legal-doctrine authority — this
    # is the dataset's topic tag (e.g. "المنع من سماع الدعوى"), useful for
    # routing but not a verified legal principle statement.
    source_topic_label: str = UNKNOWN

    def to_dict(self) -> dict:
        return {
            "resource_family": "judicial",
            "jurisdiction": self.jurisdiction,
            "judicial_system": self.judicial_system,
            "court": self.court,
            "court_level": self.court_level,
            "chamber": self.chamber,
            "case_type": self.case_type,
            "appeal_number": self.appeal_number,
            "judicial_year": self.judicial_year,
            "decision_date": self.decision_date,
            "technical_office": self.technical_office,
            "page": self.page,
            "citation": self.citation,
            "source_topic_label": self.source_topic_label,
        }


@dataclass
class SourceProvenance:
    """Corpus-source provenance, kept separate from primary-authority
    provenance per the master prompt's "do not collapse both into one
    source" instruction."""

    corpus_source: str = UNKNOWN  # e.g. "dataflare/egypt-legal-corpus"
    corpus_source_revision: str | None = None  # e.g. file SHA-256
    primary_authority_source: str = UNKNOWN  # e.g. official gazette — usually unknown here
    provenance_status: str = ProvenanceStatus.UNKNOWN.value
    license_state: str = UNKNOWN

    def to_dict(self) -> dict:
        return {
            "corpus_source": self.corpus_source,
            "corpus_source_revision": self.corpus_source_revision,
            "primary_authority_source": self.primary_authority_source,
            "provenance_status": self.provenance_status,
            "license_state": self.license_state,
        }


__all__ = [
    "UNKNOWN",
    "ProvenanceStatus",
    "LegislativeIdentity",
    "JudicialIdentity",
    "SourceProvenance",
]
