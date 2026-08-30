# Legal Intelligence Engine

Repository: https://github.com/enghassanelhabbal-DevOps/Legal_Intelligence_Enginev3

Active engineering branch: `feat/enterprise-foundation`

An evidence-first, jurisdiction-aware, version-aware, resource-efficient Legal Intelligence Platform for Arabic legal systems, starting with Egypt.

This project is not a generic legal chatbot. The engineering goal is to build trustworthy legal knowledge, retrieval, evidence, temporal/jurisdiction correctness, grounded reasoning, abstention, auditability, and measurable reliability.

## Start here

1. Read `ARCHITECTURE_CONTRACT.md` — authoritative architecture.
2. Read `CLAUDE.md` / `COPILOT.md` — coding-agent rules.
3. Read `docs/FOUNDATION_INDEX.md` — documentation hierarchy.
4. Read `docs/REPOSITORY_STRUCTURE.md` — clean repository layout.
5. For current Stage 1 execution, read `docs/CLAUDE_EXECUTION_MASTER.md`.

## Canonical entry points

- API: `api/app.py`
- Streamlit UI: `ui/streamlit_app.py`
- Core package: `src/legal_ai/`
- Tests: `tests/`
- Evaluation assets: `data/evaluation/`
- Reproducible artifacts/reports: `artifacts/`

The root `app.py` is known Stage 3 consolidation debt. Do not add new retrieval/generation business logic there.

## Current architecture

```text
UI / API
   ↓
services
   ↓
retrieval → reranking → evidence → generation
      ↑
 knowledge ← ingestion
      ↑
 evaluation / data governance

Cross-cutting: resource policy, failure handling, observability, security
```

## Current engineering stage

The project is completing **Stage 1 — Dataset Intake + Evaluation Foundation**, including Dataflare corpus archaeology, legal-resource identity, document-type classification, provenance, duplicate clustering, leakage-safe grouping, dataset manifests, and independent evaluation preparation.

Stage 1 does not authorize model fine-tuning or broad retrieval optimization. Measurement comes first.

## Development setup

```bash
python -m venv .venv
# activate for your OS
python -m pip install -U pip
python -m pip install -e ".[dev]"
pytest
```

Optional local-model/GPU support:

```bash
python -m pip install -e ".[qwen,gpu]"
```

See:

- `docs/runbooks/GPU_SETUP.md`
- `docs/runbooks/PORTABILITY.md`
- `docs/runbooks/BACKEND_DEPLOY.md`
- `docs/runbooks/LOCAL_QWEN.md` when present
- `docs/runbooks/WSL_TESTING.md` when present

## Evaluation truth

The historical retrieval figure `MRR=0.835` is an **UNVERIFIED HISTORICAL REFERENCE**, not a current release gate.

The current BM25 self-retrieval smoke benchmark is a regression guard only and is not proof of Egyptian legal understanding.

Full dense + lexical + reranker production-path benchmarking belongs to Stage 4.

## Data / artifact policy

Large corpora, embeddings, and indexes should be versioned with DVC/external storage rather than committed as raw binaries. Machine-readable reports and small controlled fixtures may live in Git when appropriate.

Raw legal source text must be preserved. Normalized/chunked text is a derived retrieval representation, not the legal authority.

## Repository hygiene

The root is intentionally small. Historical architecture drafts and superseded promotion files are removed from the working tree because Git history is the archive.

Before adding a new top-level file/package, read `docs/REPOSITORY_STRUCTURE.md` and reuse the canonical location whenever possible.
