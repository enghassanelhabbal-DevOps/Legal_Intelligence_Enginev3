import argparse
import json
import logging
import sys
from pathlib import Path

# Force UTF-8 for Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]

from src.legal_ai.core.config import set_seed
from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
from src.legal_ai.services.query_service import QueryService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Portable GPU-accelerated Legal RAG retrieval core"
    )
    parser.add_argument("--documents", default="legal_documents.json")
    parser.add_argument("--output", default="artifacts_portable")
    parser.add_argument("--query", default="ما شروط القبض على المتهم في حالة التلبس؟")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--precision", choices=["auto", "fp32", "fp16", "bf16"], default="auto")
    parser.add_argument("--dense-batch-size", type=int, default=32)
    parser.add_argument("--rerank-batch-size", type=int, default=32)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--dense-candidates", type=int, default=30)
    parser.add_argument("--bm25-candidates", type=int, default=10)
    parser.add_argument("--rerank-candidates", type=int, default=40)
    parser.add_argument("--rerank-max-chars", type=int, default=4500)
    parser.add_argument("--alpha", type=float, default=0.75)
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--compile-reranker", action="store_true")
    parser.add_argument("--no-reranker", action="store_true")
    parser.add_argument(
        "--generate", action="store_true",
        help="Run full RAG pipeline including LLM generation",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    set_seed()

    docs_path = Path(args.documents)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # We use query service instead of prepare_pipeline directly
    runtime = RuntimeConfig(
        device=args.device,
        gpu_id=args.gpu_id,
        precision=args.precision,
        dense_batch_size=args.dense_batch_size,
        rerank_batch_size=args.rerank_batch_size,
        max_seq_length=args.max_seq_length,
        compile_reranker=args.compile_reranker,
    )
    pipeline_cfg = PipelineConfig(
        dense_candidates=args.dense_candidates,
        bm25_candidates=args.bm25_candidates,
        rerank_candidates=args.rerank_candidates,
        final_k=args.top_k,
        rerank_max_chars=args.rerank_max_chars,
        alpha=args.alpha,
    )

    query_service = QueryService.from_json(
        documents_path=docs_path,
        runtime=runtime,
        pipeline_cfg=pipeline_cfg,
        artifact_dir=out_dir,
        load_reranker=not args.no_reranker,
        llm_config=None
    )

    if args.generate:
        print("\n=== Running Full RAG Pipeline (LLM Generation) ===")
        answer = query_service.answer(args.query, top_k=args.top_k)
        from dataclasses import asdict
        print(json.dumps(asdict(answer), ensure_ascii=False, indent=2))
    else:
        # For pure retrieval backwards compatibility with old script
        result = query_service.retrieve(args.query, top_k=args.top_k)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    query_service.close()

if __name__ == "__main__":
    main()
