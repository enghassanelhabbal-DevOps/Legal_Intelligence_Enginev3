"""exceptions.py — Typed exception hierarchy for the Legal AI platform.

Rule: never swallow exceptions silently (ARCHITECTURE_CONTRACT.md §Clean code rule 7).
Raise one of these typed exceptions from each layer so callers can handle selectively.
"""

from __future__ import annotations


class LegalAIError(Exception):
    """Base exception for all Legal AI platform errors."""


class IngestionError(LegalAIError):
    """Raised when document parsing, normalization, or validation fails."""


class RetrievalError(LegalAIError):
    """Raised when the retrieval pipeline fails (dense, BM25, or fusion)."""


class RerankerError(LegalAIError):
    """Raised when the reranker / cross-encoder fails."""


class EvidenceError(LegalAIError):
    """Raised when evidence selection or context building fails."""


class GenerationError(LegalAIError):
    """Raised when the LLM generation step fails."""


class EvaluationError(LegalAIError):
    """Raised when an evaluation metric or benchmark step fails."""


class DatasetManifestError(LegalAIError):
    """Raised for dataset manifest schema, provenance, or license-state problems.

    Deliberately covers schema/provenance/license as one category: all three
    are "the manifest is not trustworthy enough to use" failures, and Stage 1
    explicitly avoids over-creating exception classes for that single concept.
    """


class DatasetLeakageError(LegalAIError):
    """Raised when a held-out/benchmark split would be contaminated."""


class DatasetSplitError(LegalAIError):
    """Raised when a requested split cannot be produced deterministically or safely."""


class ConfigError(LegalAIError):
    """Raised for missing or invalid configuration values."""


__all__ = [
    "LegalAIError",
    "IngestionError",
    "RetrievalError",
    "RerankerError",
    "EvidenceError",
    "GenerationError",
    "EvaluationError",
    "DatasetManifestError",
    "DatasetLeakageError",
    "DatasetSplitError",
    "ConfigError",
]
