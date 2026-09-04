"""Legal AI Platform — top-level package.

Sub-packages follow the ARCHITECTURE_CONTRACT.md dependency order:
  core → knowledge → ingestion → retrieval → reranking → evidence → generation
  evaluation is standalone; services orchestrates the above.
"""

__version__ = "0.2.0"

from . import core, evidence, evaluation, generation, ingestion, knowledge, reranking, retrieval, services

__all__ = [
    "core",
    "knowledge",
    "ingestion",
    "retrieval",
    "reranking",
    "evidence",
    "generation",
    "evaluation",
    "services",
]
