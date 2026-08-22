"""ingestion sub-package — parsing, normalization, validation, hashing, deduplication.

Public API:
    from src.legal_ai.ingestion import normalize_arabic, tokenize
    from src.legal_ai.ingestion import article_aware_chunk, chunk_document
    from src.legal_ai.ingestion import hash_document, validate_document
"""

from src.legal_ai.ingestion.chunker import article_aware_chunk, chunk_document
from src.legal_ai.ingestion.normalization import normalize_arabic, tokenize
from src.legal_ai.ingestion.validation import hash_document, validate_document

__all__ = [
    "normalize_arabic",
    "tokenize",
    "article_aware_chunk",
    "chunk_document",
    "hash_document",
    "validate_document",
]
