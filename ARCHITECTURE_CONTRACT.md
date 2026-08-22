# ARCHITECTURE_CONTRACT.md

This is the single source of truth for the Legal Intelligence Engine architecture. All developers, Copilot, Claude Code, scripts and future agents must follow it.

## Repository

```text
legal-intelligence-engine/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── CLAUDE.md
├── COPILOT.md
├── ARCHITECTURE_CONTRACT.md
├── TEAM_OWNERSHIP.md
├── configs/
│   ├── base.yaml
│   ├── local.yaml
│   └── test.yaml
├── data/
│   ├── raw/
│   ├── normalized/
│   └── evaluation/
├── artifacts/
│   ├── embeddings/
│   ├── indexes/
│   └── reports/
├── src/legal_ai/
│   ├── core/
│   ├── knowledge/
│   ├── ingestion/
│   ├── retrieval/
│   ├── reranking/
│   ├── evidence/
│   ├── generation/
│   ├── evaluation/
│   └── services/
├── api/app.py
├── ui/app.py
├── scripts/
├── tests/
└── docs/
```

## Ownership

- `core/`: config, runtime, models, exceptions, logging.
- `knowledge/`: legal schema, provenance, versions.
- `ingestion/`: parsing, normalization, validation, hashing, deduplication.
- `retrieval/`: BGE-M3, FAISS, BM25, candidate fusion, filters.
- `reranking/`: cross-encoder and scoring.
- `evidence/`: evidence selection, context building, citation validation.
- `generation/`: LLM interface and implementations such as Qwen.
- `evaluation/`: metrics, benchmarks, regression.
- `services/`: orchestration only.
- `api/`: HTTP only.
- `ui/`: presentation only.

## Dependency flow

```text
API/UI → services → retrieval → reranking → evidence → generation
                         ↑
                    knowledge ← ingestion
                         ↓
                    evaluation
```

Do not put retrieval inside the LLM layer or LLM code inside retrieval.

## Contracts

```python
@dataclass
class LegalDocument:
    document_id: str
    jurisdiction: str
    law_id: str
    law_name: str
    article_id: str
    raw_text: str
    normalized_text: str
    embedding_text: str
    version_id: str | None
    source: str | None
```

```python
@dataclass
class RetrievalResult:
    document_id: str
    score: float
    law_name: str
    article_id: str
    text: str
    source: str | None
    version_id: str | None
```

```python
@dataclass
class Answer:
    answer: str
    citations: list[dict]
    evidence: list[dict]
    warnings: list[str]
    timing: dict
```

## Protected retrieval baseline

Current known baseline:

- MRR: 0.835
- Recall@1: 0.75
- Recall@3: 0.90
- Recall@5: 0.95
- Recall@10: 1.00

Any retrieval/reranker change must report before/after metrics and latency.

## ML rules

Default flow:

```text
Query
→ Dense Retrieval (BGE-M3)
→ BM25 supplementary retrieval
→ Dense-preserving candidate union
→ Reranker
→ Evidence selection
→ LLM
```

Reranking must use batch inference. Do not reintroduce the old RRF behavior as the default without evidence that it improves the protected baseline.

## Hardware

Development target:
- Windows 10
- NVIDIA Quadro M2200
- 4 GB VRAM
- Compute Capability 5.2
- Python 3.12

Treat GPU memory as scarce. Keep FAISS/BM25 on CPU where appropriate. Avoid keeping multiple large transformer models on GPU at the same time.

## Clean code

1. One responsibility per module.
2. Type hints on public APIs.
3. Small functions.
4. No magic numbers.
5. No hard-coded paths.
6. No global mutable state.
7. No silent exception swallowing.
8. No duplicate business logic.
9. No unnecessary dependencies.
10. New behavior needs tests.
11. ML changes need benchmarks.
12. No premature microservices.

## Two-day MVP

Implement only:
- canonical schema
- normalization
- dense retrieval
- BM25
- candidate fusion
- reranking
- evidence layer
- Qwen adapter
- query service
- API
- simple UI
- evaluation
- basic tests
- health check

Defer:
- full knowledge version graph
- full MLOps
- Kubernetes
- microservices
- fine-tuning
- multi-country rollout
