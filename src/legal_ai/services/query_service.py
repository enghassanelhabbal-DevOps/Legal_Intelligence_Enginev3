"""query_service.py — High-level orchestration service.

Thin orchestrator: wires retrieval → evidence → generation.
No business logic lives here (ARCHITECTURE_CONTRACT.md §Ownership: services = orchestration only).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.legal_ai.core.contracts import Answer
from src.legal_ai.core.logging import get_logger
from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
from src.legal_ai.evidence import build_grounded_context, select_evidence, validate_citations
from src.legal_ai.generation import LLMManager
from src.legal_ai.ingestion.validation import validate_documents
from src.legal_ai.retrieval import prepare_pipeline

LOGGER = get_logger(__name__)


class QueryService:
    """Orchestrates a full query: retrieve → evidence → generate → validate citations.

    This replaces the old RAGService in legal_ai/service.py.
    """

    def __init__(
        self,
        documents: list[dict[str, Any]],
        runtime: RuntimeConfig,
        pipeline_cfg: PipelineConfig,
        artifact_dir: Path,
        load_reranker: bool = True,
        llm_config: dict[str, Any] | None = None,
    ) -> None:
        validate_documents(documents)
        self.pipeline_cfg = pipeline_cfg
        self.artifact_dir = artifact_dir

        LOGGER.info("Preparing retrieval pipeline …")
        self.retriever, self.runtime_info = prepare_pipeline(
            documents, runtime, pipeline_cfg, artifact_dir, load_reranker=load_reranker
        )
        self.llm = LLMManager(config=llm_config or {})

    @classmethod
    def from_json(
        cls,
        documents_path: Path,
        runtime: RuntimeConfig,
        pipeline_cfg: PipelineConfig,
        artifact_dir: Path,
        load_reranker: bool = True,
        llm_config: dict[str, Any] | None = None,
    ) -> QueryService:
        import json

        with documents_path.open("r", encoding="utf-8") as f:
            docs = json.load(f)
        return cls(docs, runtime, pipeline_cfg, artifact_dir, load_reranker, llm_config)

    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        """Run retrieval only (no LLM)."""
        return self.retriever.retrieve(query, top_k=top_k or self.pipeline_cfg.final_k)

    def answer(self, query: str, top_k: int | None = None) -> Answer:
        """Full pipeline: retrieve → evidence → generate → validate."""
        t0 = time.perf_counter()

        retrieval = self.retrieve(query, top_k=top_k)
        evidence = select_evidence(retrieval["results"], max_chars=self.pipeline_cfg.max_context_chars)
        context = build_grounded_context(evidence, max_chars=self.pipeline_cfg.max_context_chars)

        t1 = time.perf_counter()

        if self.llm.backend is None:
            self.llm.load()
        raw_answer = self.llm.generate(query, context)

        t2 = time.perf_counter()

        # Try to parse structured JSON from LLM response
        citations: list[dict] = []
        warnings: list[str] = []
        try:
            import json
            parsed = json.loads(raw_answer)
            citations = parsed.get("citations", [])
            warnings = parsed.get("warnings", [])
            raw_answer = parsed.get("answer", raw_answer)
        except Exception:
            warnings.append("LLM response was not valid JSON; raw text returned.")

        # Citation validation
        citation_warnings = validate_citations(citations, evidence)
        warnings.extend(citation_warnings)

        return Answer(
            answer=raw_answer,
            citations=citations,
            evidence=evidence,
            warnings=warnings,
            timing={
                "retrieval_ms": (t1 - t0) * 1000,
                "generation_ms": (t2 - t1) * 1000,
                "total_ms": (t2 - t0) * 1000,
            },
        )

    def close(self) -> None:
        """Release GPU memory explicitly."""
        import gc

        import torch

        self.llm.unload()
        for attr in ("encoder", "reranker"):
            obj = getattr(self.retriever, attr, None)
            if obj is not None:
                try:
                    obj.model.to("cpu")
                    del obj.model
                except Exception:
                    pass
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


__all__ = ["QueryService"]
