"""build_eval_set.py — Build a reproducible retrieval evaluation set from the REAL corpus.

Why this exists
----------------
The previous regression harness measured retrieval quality against a hand-written
3-sentence synthetic corpus that could never fail. This script instead builds an
evaluation set from `legal_documents.json` itself.

Methodology (self-retrieval smoke set — read this before trusting the numbers)
--------------------------------------------------------------------------------
For a deterministic, seeded sample of N real articles, we extract the first
sentence/clause of each article's `raw_text` as a "query" and record that
article's own `document_id` as the single ground-truth relevant document.
We then check whether the retrieval pipeline can find the article a real user
query would plausibly be about, using only a fragment of it as the probe.

This is a SELF-RETRIEVAL SMOKE TEST, not a human-labeled IR benchmark:
  - It WILL catch gross regressions: broken tokenization, a corrupted index,
    a fusion bug that drops the obviously-correct candidate, an off-by-one in
    ranking, etc.
  - It will NOT tell you whether the system handles paraphrased user questions,
    multi-article questions, or genuinely ambiguous queries as well as a human
    would expect — that requires a real human-labeled evaluation set, which does
    not exist yet in this repository (see BUILD NEXT in the review report).

Usage:
    python scripts/build_eval_set.py \
        --documents legal_documents.json \
        --output data/evaluation/eval_queries.json \
        --sample-size 80 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path


def _extract_query(raw_text: str, max_chars: int = 140) -> str | None:
    """Pull a short, query-like fragment out of an article's raw text."""
    text = re.sub(r"^\s*المادة\s*\S*\s*[-:]?\s*", "", raw_text or "").strip()
    if not text:
        return None
    # Cut at the first sentence terminator, capped at max_chars.
    match = re.search(r"[.\u06D4؟!]", text)
    end = match.start() if match else len(text)
    fragment = text[: min(end, max_chars)].strip()
    return fragment if len(fragment) >= 15 else None


def build_eval_set(documents: list[dict], sample_size: int, seed: int) -> list[dict]:
    candidates = []
    for doc in documents:
        query = _extract_query(doc.get("raw_text", ""))
        if query:
            candidates.append(
                {
                    "query": query,
                    "relevant_document_ids": [str(doc.get("document_id"))],
                    "law_name": doc.get("law_name", ""),
                    "article_id": doc.get("article_id", ""),
                }
            )

    rng = random.Random(seed)
    rng.shuffle(candidates)
    return candidates[: min(sample_size, len(candidates))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", default="legal_documents.json")
    parser.add_argument("--output", default="data/evaluation/eval_queries.json")
    parser.add_argument("--sample-size", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    documents = json.loads(Path(args.documents).read_text(encoding="utf-8"))
    eval_set = build_eval_set(documents, args.sample_size, args.seed)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "methodology": "self_retrieval_smoke_v1",
                "source_corpus": args.documents,
                "sample_size": len(eval_set),
                "seed": args.seed,
                "queries": eval_set,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(eval_set)} evaluation queries to {out_path}")


if __name__ == "__main__":
    main()
