"""knowledge sub-package — legal schema, provenance, embedding cache, versioning.

Public API:
    from src.legal_ai.knowledge import KnowledgeVersion, EmbeddingCache
    from src.legal_ai.knowledge import list_versions, rollback_to
"""

from src.legal_ai.knowledge.cache import EmbeddingCache, EmbeddingCacheJSON, EmbeddingCacheLMDB
from src.legal_ai.knowledge.versioning import KnowledgeVersion, list_versions, rollback_to

__all__ = [
    "KnowledgeVersion",
    "EmbeddingCache",
    "EmbeddingCacheJSON",
    "EmbeddingCacheLMDB",
    "list_versions",
    "rollback_to",
]
