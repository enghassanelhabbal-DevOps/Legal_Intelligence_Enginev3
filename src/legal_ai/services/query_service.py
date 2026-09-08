"""query_service.py — High-level orchestration service.

Thin orchestrator: wires retrieval → evidence → generation.
No business logic lives here (ARCHITECTURE_CONTRACT.md §Ownership: services = orchestration only).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.legal_ai.core.contracts import Answer
from src.legal_ai.core.logging import get_logger
from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
from src.legal_ai.evidence import build_grounded_context, select_evidence, validate_citations
from src.legal_ai.generation import LLMManager
from src.legal_ai.ingestion.validation import validate_documents

if TYPE_CHECKING:
    # Only imported for static type-checking — runtime.plan is torch-free
    # itself, but importing it eagerly here would still be an unnecessary
    # module-load-order coupling for a class whose whole point is staying
    # importable before any runtime/profile decision has been made.
    from src.legal_ai.runtime.plan import ResolvedRuntimePlan

# `prepare_pipeline`/`prepare_pipeline_from_plan` are deliberately NOT
# imported at module level: `src.legal_ai.retrieval`'s `__getattr__`
# (PEP 562) only defers torch/faiss loading past *that* module's import —
# a top-level `from src.legal_ai.retrieval import prepare_pipeline` here
# would immediately trigger it anyway, forcing torch on every
# `import query_service`, including BM25-only/remote-generation-only
# deployments that never call it (DR-032 / Stage 2 packaging gate).

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
        from src.legal_ai.retrieval import prepare_pipeline  # noqa: PLC0415

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

    @classmethod
    def from_plan(
        cls,
        documents: list[dict[str, Any]],
        plan: ResolvedRuntimePlan,
        artifact_dir: Path,
        pipeline_cfg: PipelineConfig | None = None,
        llm_config: dict[str, Any] | None = None,
    ) -> QueryService:
        """Construct a `QueryService` from a centrally-resolved
        `ResolvedRuntimePlan` (see `runtime.plan.resolve_runtime_plan()`)
        instead of hand-built `RuntimeConfig`/`PipelineConfig`/generation
        config. Device, batch sizes, candidate counts, and generation
        timeout are all derived from the single plan resolution rather
        than independently guessed here — retrieval/generation logic
        itself is unchanged, only how it is configured.

        `plan` is typed via a `TYPE_CHECKING`-only forward reference
        (`ResolvedRuntimePlan`) so static type-checking is accurate without
        this lightweight-importable module acquiring a hard, module-level
        runtime dependency on `runtime.plan` for callers that never use
        this constructor path.
        """
        instance = object.__new__(cls)
        validate_documents(documents)
        instance.pipeline_cfg = plan.to_pipeline_config(pipeline_cfg)
        instance.artifact_dir = artifact_dir

        LOGGER.info(
            "Preparing retrieval pipeline from ResolvedRuntimePlan (profile=%s) …", plan.profile
        )
        from src.legal_ai.retrieval import prepare_pipeline_from_plan  # noqa: PLC0415

        instance.retriever, instance.runtime_info = prepare_pipeline_from_plan(
            documents, plan, artifact_dir, instance.pipeline_cfg
        )
        instance.runtime_info["resolved_runtime_plan"] = plan.to_dict()
        instance.llm = LLMManager(config=plan.to_generation_config(llm_config))
        return instance

    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        """Run retrieval only (no LLM)."""
        return self.retriever.retrieve(query, top_k=top_k or self.pipeline_cfg.final_k)

    def answer(self, query: str, top_k: int | None = None) -> Answer:
        """Full pipeline: retrieve → evidence → generate → validate."""
        t0 = time.perf_counter()

        retrieval = self.retrieve(query, top_k=top_k)
        max_chars = self.pipeline_cfg.max_context_chars
        evidence = select_evidence(retrieval["results"], max_chars=max_chars)
        context = build_grounded_context(evidence, max_chars=max_chars)

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
        """Release GPU memory explicitly. Best-effort and lightweight-safe:

        - Never imports/requires torch merely to shut down. A REMOTE_LLM
          deployment with no dense extra installed must be able to close()
          cleanly (Risk 2 / DR-036) — this only imports torch lazily, and
          only if a torch-backed component (encoder/reranker) was actually
          loaded onto this instance.
        - Never performs a fresh, unprotected `torch.cuda.is_available()`
          probe as a way to decide what to clean up — that decision comes
          from which components this instance actually has, not a new
          global hardware check (the isolated subprocess probe in
          `runtime.hardware` remains the only sanctioned CUDA discovery
          path; this method does not duplicate it).
        - Per-component cleanup failures are logged and shutdown continues
          — a broken GPU release must not mask the original shutdown or
          crash the process, but exceptions are not swallowed silently
          everywhere either (narrow try/except per component).
        """
        self.llm.unload()

        torch_backed_loaded = False
        for attr in ("encoder", "reranker"):
            obj = getattr(self.retriever, attr, None)
            model = getattr(obj, "model", None) if obj is not None else None
            if model is None:
                continue
            torch_backed_loaded = True
            try:
                model.to("cpu")
                del obj.model
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup must not abort shutdown
                LOGGER.warning("Failed to release %s model during shutdown: %s", attr, exc)

        if not torch_backed_loaded:
            return  # lightweight/REMOTE_LLM instance: nothing torch-backed was ever loaded

        import gc

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass  # torch-backed component existed but torch vanished mid-shutdown
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("CUDA cache cleanup failed during shutdown: %s", exc)


__all__ = ["QueryService"]
