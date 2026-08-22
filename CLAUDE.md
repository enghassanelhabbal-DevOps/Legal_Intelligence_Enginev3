# CLAUDE.md

Read `ARCHITECTURE_CONTRACT.md` and `TEAM_OWNERSHIP.md` before changing code.

`ARCHITECTURE_CONTRACT.md` is the single source of truth.

## Rules

- Work incrementally. Do not rewrite the repository.
- Reuse existing modules before creating new ones.
- Put code only in the module that owns the responsibility.
- Retrieval code belongs in `retrieval/`.
- Reranker code belongs in `reranking/`.
- Legal parsing belongs in `ingestion/`.
- Legal schema/provenance belongs in `knowledge/`.
- Evidence/citations belong in `evidence/`.
- LLM/Qwen belongs in `generation/`.
- Orchestration belongs in `services/`.
- API/UI must not contain ML implementation details.

## Baseline

Protect:
- MRR 0.835
- Recall@1 0.75
- Recall@5 0.95
- Recall@10 1.00

Every ML change must report metric and latency deltas.

## Hardware

Target: NVIDIA Quadro M2200 4GB, SM 5.2.

Do not assume Tensor Cores or FP8 acceleration. Manage GPU memory explicitly and avoid model co-residency when possible.

## Coding

Use Python 3.12, pathlib, typed models, explicit exceptions, structured logging and deterministic behavior.

Avoid magic numbers, global mutable state, broad exception swallowing, hard-coded paths and duplicated utilities.

After changes run targeted tests. For ML work also run the relevant benchmark.

Stop before architectural changes, new top-level directories, new platform-specific dependencies, or legal-data behavior that is ambiguous.
