# COPILOT.md

Read `ARCHITECTURE_CONTRACT.md` before editing.

## Ownership map

| Area | Location |
|---|---|
| Config/runtime | `src/legal_ai/core/` |
| Legal schema | `src/legal_ai/knowledge/` |
| Ingestion | `src/legal_ai/ingestion/` |
| Dense/BM25/fusion | `src/legal_ai/retrieval/` |
| Reranker | `src/legal_ai/reranking/` |
| Evidence/citations | `src/legal_ai/evidence/` |
| Qwen/LLM | `src/legal_ai/generation/` |
| Orchestration | `src/legal_ai/services/` |
| Evaluation | `src/legal_ai/evaluation/` |
| HTTP | `api/` |
| UI | `ui/` |

## Required behavior

- Make the smallest clean change.
- Reuse existing modules.
- Add tests for new behavior.
- Benchmark retrieval/reranker changes.
- Preserve the Dense baseline unless improvement is measured.
- Keep Qwen isolated from retrieval.
- Keep API/UI free of model internals.
- Avoid new dependencies unless justified.

## Never

- create duplicate `utils` or retriever modules
- move architecture casually
- hard-code Windows paths
- put prompts in retrieval
- put FAISS in the API
- put Qwen in the UI
- add microservices/Kubernetes during MVP
- silently change the retrieval strategy
- silently catch errors

Known baseline:
MRR 0.835, Recall@1 0.75, Recall@5 0.95, Recall@10 1.00.
