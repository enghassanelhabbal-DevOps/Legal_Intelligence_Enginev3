"""regression_harness.py — Measure REAL retrieval quality against the REAL corpus.

Replaces the previous harness, which built a 3-sentence synthetic corpus with
hand-crafted embeddings and imported BM25/DenseIndex from the legacy
`legal_rag_engine.py` monolith (deleted in this consolidation). That harness
could never fail and never touched `src/legal_ai/`.

This harness:
  1. Loads the real `legal_documents.json` corpus (952 articles).
  2. Loads the evaluation set produced by `scripts/build_eval_set.py`
     (`data/evaluation/eval_queries.json` — see that script's docstring for
     the self-retrieval-smoke-test methodology and its limits).
  3. Runs the actual `src.legal_ai.retrieval.bm25.BM25` engine (imported from
     the real package, not a duplicate) against every evaluation query.
  4. Computes MRR / Recall@1/3/5/10 with `src.legal_ai.evaluation.metrics`
     (the same functions the protected baseline references).
  5. Writes `artifacts/reports/regression_baseline.json` with full metadata
     for traceability (corpus size, eval-set size, seed, git-independent
     content hash of the corpus).

This is the FAST tier: BM25-only, pure NumPy, no model downloads — safe to run
on every PR in a few seconds. A full hybrid (dense + BM25 + reranker) run
against the same eval set can be added as a slower, separately-triggered CI
job once the dense/rerank models are cached in CI (see docs — not implemented
here to avoid silently downloading large models in this review pass).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.legal_ai.evaluation.metrics import mean_mrr, mean_recall_at_k
from src.legal_ai.ingestion.normalization import normalize_arabic, tokenize
from src.legal_ai.retrieval.bm25 import BM25


def _corpus_hash(documents: list[dict]) -> str:
    ids = "|".join(str(d.get("document_id")) for d in documents)
    return hashlib.sha256(ids.encode("utf-8")).hexdigest()[:16]


def run_harness(documents_path: Path, eval_set_path: Path, top_k: int = 10) -> dict:
    documents = json.loads(documents_path.read_text(encoding="utf-8"))
    eval_data = json.loads(eval_set_path.read_text(encoding="utf-8"))
    eval_queries = eval_data["queries"]

    doc_ids = [str(d.get("document_id")) for d in documents]
    corpus_tokens = [
        tokenize(normalize_arabic(d.get("normalized_text") or d.get("raw_text", "")))
        for d in documents
    ]

    t0 = time.perf_counter()
    bm25 = BM25(corpus_tokens)
    build_ms = (time.perf_counter() - t0) * 1000

    per_query_results = []
    t1 = time.perf_counter()
    for item in eval_queries:
        hits = bm25.top_n(item["query"], n=top_k)
        retrieved_ids = [doc_ids[idx] for idx, _score in hits]
        per_query_results.append(
            {"retrieved": retrieved_ids, "relevant": item["relevant_document_ids"]}
        )
    query_ms = (time.perf_counter() - t1) * 1000

    report = {
        "engine": "src.legal_ai.retrieval.bm25.BM25",
        "corpus_documents": len(documents),
        "corpus_hash": _corpus_hash(documents),
        "eval_set_size": len(eval_queries),
        "eval_set_methodology": eval_data.get("methodology", "unknown"),
        "index_build_ms": round(build_ms, 2),
        "total_query_ms": round(query_ms, 2),
        "avg_query_ms": round(query_ms / max(1, len(eval_queries)), 3),
        "metrics": {
            "MRR": round(mean_mrr(per_query_results), 4),
            "Recall@1": round(mean_recall_at_k(per_query_results, 1), 4),
            "Recall@3": round(mean_recall_at_k(per_query_results, 3), 4),
            "Recall@5": round(mean_recall_at_k(per_query_results, 5), 4),
            "Recall@10": round(mean_recall_at_k(per_query_results, 10), 4),
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", default="legal_documents.json")
    parser.add_argument("--eval-set", default="data/evaluation/eval_queries.json")
    parser.add_argument("--output", default="artifacts/reports/regression_baseline.json")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    report = run_harness(Path(args.documents), Path(args.eval_set), args.top_k)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWrote report to {out_path}")


if __name__ == "__main__":
    main()
