"""core sub-package — config, runtime, models, exceptions, logging.

Public API:
  from src.legal_ai.core import LegalDocument, RetrievalResult, Answer
  from src.legal_ai.core import RuntimeConfig, PipelineConfig
  from src.legal_ai.core.config import load_config, load_runtime_config
"""

from src.legal_ai.core.config import load_config, load_runtime_config
from src.legal_ai.core.contracts import Answer, LegalDocument, RetrievalResult
from src.legal_ai.core.exceptions import (
    GenerationError,
    IngestionError,
    LegalAIError,
    RetrievalError,
)
from src.legal_ai.core.logging import get_logger
from src.legal_ai.core.models import (
    LLMBackend,
    PipelineConfig,
    RAGServiceProtocol,
    RetrievalHit,
    RuntimeConfig,
)

__all__ = [
    # Contracts (canonical dataclasses)
    "LegalDocument",
    "RetrievalResult",
    "Answer",
    # Runtime / pipeline configs
    "RuntimeConfig",
    "PipelineConfig",
    "RetrievalHit",
    # Protocols
    "LLMBackend",
    "RAGServiceProtocol",
    # Config loaders
    "load_config",
    "load_runtime_config",
    # Exceptions
    "LegalAIError",
    "IngestionError",
    "RetrievalError",
    "GenerationError",
    # Logging
    "get_logger",
]
