"""api/app.py — Thin FastAPI service over the Legal RAG Engine.

Design rules enforced here (see ARCHITECTURE_CONTRACT.md):
  - The API owns HTTP concerns only (auth, rate limiting, request/response
    shape, error mapping). All retrieval/evidence/generation orchestration
    lives in `QueryService.answer()` — this file must never re-implement it.
  - `QueryService` and `LLMManager` are built ONCE at startup (FastAPI
    `lifespan`) and reused for every request. The previous version of this
    file constructed both from scratch inside the request handler, which
    meant every single query reloaded the retrieval index and the LLM —
    unusable under any real load. That bug is fixed here.
  - Ingested documents are validated against the canonical `LegalDocument`
    schema before being written anywhere.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.legal_ai.core.config import set_seed
from src.legal_ai.core.exceptions import IngestionError
from src.legal_ai.core.logging import get_logger
from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
from src.legal_ai.ingestion.validation import validate_documents
from src.legal_ai.services.query_service import QueryService

LOGGER = get_logger(__name__)

DOCUMENTS_PATH = Path(os.environ.get("DOCUMENTS_PATH", "legal_documents.json"))
ARTIFACT_DIR = Path(os.environ.get("ARTIFACT_DIR", "artifacts"))
API_KEY = os.environ.get("API_KEY")
LOAD_RERANKER = os.environ.get("LOAD_RERANKER", "0").strip().lower() in {"1", "true", "yes"}

# Populated once at startup by the lifespan handler below; never rebuilt per-request.
_state: dict[str, Any] = {"service": None, "startup_error": None, "started_at": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_seed()
    LOGGER.info("Starting up: loading documents from %s", DOCUMENTS_PATH)
    try:
        if not DOCUMENTS_PATH.exists():
            raise FileNotFoundError(f"Documents file not found: {DOCUMENTS_PATH}")
        documents = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
        runtime = RuntimeConfig()
        pipeline_cfg = PipelineConfig()
        _state["service"] = QueryService(
            documents=documents,
            runtime=runtime,
            pipeline_cfg=pipeline_cfg,
            artifact_dir=ARTIFACT_DIR,
            load_reranker=LOAD_RERANKER,
        )
        _state["started_at"] = time.time()
        LOGGER.info("Startup complete: %d documents indexed.", len(documents))
    except Exception as exc:  # noqa: BLE001 - we want /v1/ready to report this, not crash boot
        LOGGER.exception("Startup failed")
        _state["startup_error"] = str(exc)

    yield

    service = _state.get("service")
    if service is not None:
        LOGGER.info("Shutting down: releasing model memory.")
        service.close()


app = FastAPI(title="Legal RAG API", version="0.3.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory sliding window; fine for a single-process
# deployment — swap for a shared store like Redis before scaling to N workers)
# ---------------------------------------------------------------------------
_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = int(os.environ.get("API_RATE_LIMIT", "30"))
_rate_state: dict[str, tuple[int, int]] = {}


def _rate_limited(key: str) -> bool:
    now = int(time.time())
    window_start = now - _RATE_LIMIT_WINDOW
    data = _rate_state.get(key)
    if data is None or data[0] < window_start:
        _rate_state[key] = (now, 1)
        return False
    ts, count = data
    if count >= _RATE_LIMIT_MAX:
        return True
    _rate_state[key] = (ts, count + 1)
    return False


def _require_api_key(x_api_key: str | None) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _get_service() -> QueryService:
    service = _state.get("service")
    if service is None:
        detail = _state.get("startup_error") or "Service not initialized yet."
        raise HTTPException(status_code=503, detail=f"Service unavailable: {detail}")
    return service


# ---------------------------------------------------------------------------
# Request / response contracts (stable — do not rename fields without a
# version bump; the Streamlit UI and any external client depend on this shape)
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    top_k: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    law_name: str = ""
    article_id: str = ""
    text: str = ""
    document_id: str | None = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    timing: dict[str, float] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/v1/health")
def health() -> dict[str, Any]:
    """Liveness probe — process is up. Does NOT guarantee the model is loaded."""
    return {"status": "ok"}


@app.get("/v1/ready")
def ready() -> JSONResponse:
    """Readiness probe — the retrieval index + LLM are actually loaded and usable.

    Use this (not /v1/health) in Docker/Kubernetes/load-balancer health checks
    to avoid routing traffic to an instance that's still starting up or that
    failed to load its documents.
    """
    if _state.get("service") is not None:
        return JSONResponse({"status": "ready", "uptime_s": round(time.time() - _state["started_at"], 1)})
    return JSONResponse(
        {"status": "not_ready", "error": _state.get("startup_error")},
        status_code=503,
    )


@app.post("/v1/query", response_model=QueryResponse)
async def query(req: QueryRequest, request: Request, x_api_key: str | None = Header(None)) -> QueryResponse:
    _require_api_key(x_api_key)

    key = x_api_key or (request.client.host if request.client else "unknown")
    if _rate_limited(key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    service = _get_service()
    try:
        result = service.answer(req.query, top_k=req.top_k)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QueryResponse(
        query=req.query,
        answer=result.answer,
        citations=[Citation(**c) for c in result.citations],
        sources=result.evidence,
        warnings=result.warnings,
        timing=result.timing,
    )


@app.post("/v1/ingest")
def ingest(payload: IngestRequest, x_api_key: str | None = Header(None)) -> dict[str, Any]:
    """Validate and stage new documents. Does NOT hot-swap the live index —
    that requires an explicit redeploy/restart so a bad ingest can never
    silently corrupt a running service. See docs/runbooks/BACKEND_DEPLOY.md.
    """
    _require_api_key(x_api_key)

    try:
        validate_documents(payload.documents)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid document(s): {exc}") from exc

    staging_path = Path(os.environ.get("INGEST_STAGING_PATH", "data/staged_documents.json"))
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path.write_text(json.dumps(payload.documents, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": "staged",
        "document_count": len(payload.documents),
        "saved_to": str(staging_path),
        "note": "Documents are validated and staged, not yet live. Promote by "
        "replacing DOCUMENTS_PATH and restarting the service.",
    }
