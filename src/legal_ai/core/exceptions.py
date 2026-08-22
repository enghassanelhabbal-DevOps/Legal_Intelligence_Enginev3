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
    "ConfigError",
]
