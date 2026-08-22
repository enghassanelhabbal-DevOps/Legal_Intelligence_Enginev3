"""contracts.py — Canonical dataclasses defined in ARCHITECTURE_CONTRACT.md.

These are the single source of truth for data shapes flowing through the pipeline.
All modules must import from here; do NOT redefine these elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LegalDocument:
    """Canonical representation of an ingested legal document / article chunk."""

    document_id: str
    jurisdiction: str          # e.g. "EG", "SA", "AE"
    law_id: str                # internal law identifier
    law_name: str              # human-readable law name (Arabic)
    article_id: str            # article number or chunk identifier
    raw_text: str              # original text before any normalization
    normalized_text: str       # after Arabic normalization (for BM25 / display)
    embedding_text: str        # text actually sent to the dense encoder
    version_id: str | None = None   # KnowledgeVersion identifier
    source: str | None = None       # file path or URL of the source document


@dataclass
class RetrievalResult:
    """A single ranked candidate returned by the retrieval + reranking pipeline."""

    document_id: str
    score: float               # final score after reranking (higher = better)
    law_name: str
    article_id: str
    text: str                  # text snippet shown to the LLM and user
    source: str | None = None
    version_id: str | None = None


@dataclass
class Answer:
    """Structured response produced by the generation layer."""

    answer: str                              # grounded natural-language answer
    citations: list[dict] = field(default_factory=list)   # [{law_name, article_id, text}]
    evidence: list[dict] = field(default_factory=list)    # raw evidence chunks used
    warnings: list[str] = field(default_factory=list)     # e.g. "insufficient evidence"
    timing: dict = field(default_factory=dict)            # {"retrieval_ms": ..., "generation_ms": ...}


__all__ = ["LegalDocument", "RetrievalResult", "Answer"]
