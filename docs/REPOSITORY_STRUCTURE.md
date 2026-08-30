# Repository Structure

Repository: https://github.com/enghassanelhabbal-DevOps/Legal_Intelligence_Enginev3

Active engineering branch: `feat/enterprise-foundation`

This document defines the intended clean repository layout. The goal is to keep the root small, make canonical boundaries obvious, and prevent architecture drift.

## Root

```text
Legal_Intelligence_Enginev3/
├── ARCHITECTURE_CONTRACT.md      # authoritative architecture
├── CLAUDE.md                     # coding/review rules
├── COPILOT.md                    # concise coding-agent rules
├── README.md                     # project entry point
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .github/
├── .claude/
├── .dvc/
├── api/
├── ui/
├── src/
├── tests/
├── scripts/
├── data/
├── artifacts/
└── docs/
```

The root must not accumulate historical architecture drafts, hardware-specific README variants, ad-hoc experiment files, local machine notes, or duplicate entry points.

## Canonical source tree

```text
src/legal_ai/
├── core/          # stable contracts, config, runtime/resource policy, errors, logging
├── domain/        # legal resource identity and domain contracts when present
├── knowledge/     # provenance, authority, versions, releases
├── ingestion/     # adapters, parsing, normalization, validation, deduplication
├── retrieval/     # lexical, dense, hybrid retrieval and retrieval filters
├── reranking/     # candidate scoring only
├── evidence/      # evidence sets, support, context, citations
├── generation/    # LLM backend contracts and adapters
├── evaluation/    # datasets, metrics, manifests, leakage and benchmarks
└── services/      # orchestration only
```

Do not create duplicate business logic in `api/`, `ui/`, root `app.py`, scripts, or new utility packages.

## Documentation

```text
docs/
├── FOUNDATION_INDEX.md
├── REPOSITORY_STRUCTURE.md
├── PRODUCT_REQUIREMENTS.md
├── LEGAL_DOMAIN_SPEC.md
├── DATA_GOVERNANCE.md
├── EVALUATION_SYSTEM_SPEC.md
├── RESOURCE_RELIABILITY_SPEC.md
├── SECURITY_PRIVACY_SPEC.md
├── SYSTEM_COMPONENT_SPEC.md
├── DELIVERY_STAGE_PLAN.md
├── ENGINEERING_GOVERNANCE.md
├── ENGINEERING_DECISION_REGISTER.md
├── CLAUDE_STAGE_HANDOFF_TEMPLATE.md
├── CLAUDE_EXECUTION_MASTER.md
├── runbooks/
└── research/
```

Historical drafts and superseded promotion artifacts should not live beside authoritative documents. Git history is the archive unless a historical artifact has ongoing research value.

## Data and artifacts

`data/` contains versioned small evaluation/configuration assets. Large source corpora and model/index binaries should be DVC-managed or externally referenced according to `DATA_GOVERNANCE.md`.

`artifacts/` contains reproducible reports, index pointers, benchmark outputs, and knowledge-release metadata. Generated junk, local caches, and machine-specific files must remain ignored.

## Entry points

- Canonical API: `api/app.py`
- Canonical Streamlit UI: `ui/streamlit_app.py`
- Root `app.py`: legacy Stage 3 consolidation debt; do not add new business logic there.

## Cleanup rule

Before adding a new top-level file or package, first prove that an existing canonical location cannot own the responsibility. When consolidating, preserve useful information in the canonical document/module and remove the superseded duplicate from the working tree.
