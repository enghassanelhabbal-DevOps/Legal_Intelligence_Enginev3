# TEAM_OWNERSHIP.md

## Person 1 — Retrieval / ML

Owns:
- `src/legal_ai/retrieval/`
- `src/legal_ai/reranking/`
- `src/legal_ai/evaluation/`
- retrieval/reranking tests
- evaluation/benchmark scripts

Responsible for BGE-M3, FAISS, BM25, fusion, reranking, retrieval metrics and performance.

## Person 2 — LLM / NLP

Owns:
- `src/legal_ai/evidence/`
- `src/legal_ai/generation/`
- generation tests

Responsible for evidence selection, context, citations, Qwen backend, prompts and structured generation.

## Person 3 — Data / Knowledge

Owns:
- `src/legal_ai/knowledge/`
- `src/legal_ai/ingestion/`
- `data/`
- schema/ingestion tests

Responsible for canonical legal schema, Arabic normalization, metadata, provenance, validation, hashing and deduplication.

## Person 4 — Backend / Integration / DevOps

Owns:
- `src/legal_ai/core/`
- `src/legal_ai/services/`
- `api/`
- `ui/`
- `configs/`
- healthcheck scripts
- README/docs

Responsible for configuration, runtime/device management, orchestration, FastAPI, UI and integration.

## Shared approval required

- `ARCHITECTURE_CONTRACT.md`
- `pyproject.toml`
- `.env.example`
- new dependencies
- new top-level directories
- repository-wide refactors

## Interfaces

Data → Retrieval: `LegalDocument`

Retrieval → Evidence/Reranker: `RetrievalResult`

Evidence → LLM: grounded structured context

LLM → API: `Answer`

Do not bypass these contracts for convenience.
