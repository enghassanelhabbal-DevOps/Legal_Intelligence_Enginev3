# Research Hypotheses — Legal Intelligence Engine Technical Moat

Status: accepted research agenda for Stage 4+ (retrieval/evidence experimentation), seeded during Stage 1/Dataflare intake planning.

## Why this document exists

The product thesis is not "we trained a model on 25M Egyptian legal tokens." It is:

> A resource-efficient legal intelligence engine that understands legal structure, retrieves complete evidence, reasons over it, respects jurisdiction and legal time, and knows when it does not have enough evidence.

That thesis is only a real technical moat if specific, falsifiable claims about *how* legal-structure-aware retrieval outperforms generic RAG are actually true and *measured*, not assumed. This document is the falsifiable form of those claims. Each hypothesis has: a precise statement, what would falsify it, the experiment that tests it (cross-referenced to `docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md`'s Experiments A–E), the metric, and the minimum evidence bar before the claim may be used in product/architecture decisions.

**Governing rule (ties to DR-015 / EVALUATION_SYSTEM_SPEC.md):** no hypothesis below may be marked CONFIRMED based on the BM25 self-retrieval smoke baseline alone. Confirmation requires the Stage 4 full dense+BM25+reranker benchmark or a dedicated experiment harness built for that hypothesis specifically.

---

## H1 — Hierarchical retrieval outperforms flat retrieval on multi-article questions

**Claim:** For questions whose correct answer requires evidence from more than one article (`L5 Multi-article evidence`, `L6 Rule + exception` per EVALUATION_SYSTEM_SPEC.md's evaluation levels), a `Law → Section → Article → Passage` retrieval path achieves higher **Full Recall@K** (all required articles present in top-K, not just one) than a single flat vector/BM25 index at equal K and equal compute budget.

**Falsified if:** flat retrieval matches or beats hierarchical retrieval on Full Recall@K for multi-article questions at equal latency/memory budget, i.e. the structural narrowing adds complexity without adding recall.

**Experiment:** Experiment A (Flat vs hierarchical retrieval) from the Dataflare assessment. Requires: (a) a multi-article evaluation subset — does not exist yet, must be built as part of the protected benchmark layer (DATASET_ASSESSMENT §"Dataset-to-benchmark strategy"), not sampled from training data; (b) both a flat index and a hierarchical index built over the same corpus for a controlled comparison.

**Primary metric:** Full Recall@K (all gold articles retrieved), secondary: latency, peak RAM.

**Minimum evidence bar:** ≥30 multi-article questions, human-labeled gold evidence sets, both retrieval paths measured on identical hardware/config.

**Dependency:** requires article-level structure to exist, i.e. depends on H2's chunking approach being implemented first (`src/legal_ai/ingestion/article_segmentation.py`, Stage 1 deliverable, precision/recall not yet measured against real Dataflare text).

---

## H2 — Article-aware chunking outperforms generic chunking

**Claim:** Chunking law text at article boundaries (one chunk = one article, or one chunk = one paragraph *within* a known article) produces higher retrieval precision and cleaner evidence citations than fixed-size/sliding-window generic chunking, because generic chunks routinely split or merge legal units that have independent legal meaning.

**Falsified if:** generic chunking achieves equal or better Recall@K/precision at equal chunk-count/compute, meaning article boundaries carry no retrieval-relevant signal beyond what embeddings already capture.

**Experiment:** New experiment, not explicitly in the Dataflare doc's A–E list — needs to be added as **Experiment F**: build two chunk sets from the same law text (article-aware via `article_segmentation.py` vs fixed-size sliding window at matched average chunk length), embed both, run the same query set, compare Recall@K and citation cleanliness (does the returned chunk correspond to exactly one article, partial article, or multiple articles).

**Primary metric:** Recall@K, plus a citation-cleanliness metric: fraction of returned chunks that map to exactly one `article_id`.

**Minimum evidence bar:** must run on real Dataflare text once ingested — `article_segmentation.py` is currently validated only on synthetic fixtures (see docs/research/STAGE_1_REPORT.md); precision/recall of the segmenter itself must be measured on real data before H2 can be tested at all, since a bad segmenter would falsely make article-aware chunking look worse than it is.

**Real-data update (2026-08-28):** validated against the real full corpus. Initial synthetic-fixture-only segmenter missed 99.7% of real statute records (root cause: real text has no internal newlines; DR-022). Fixed and re-measured: 17.2% of statute-like records (56 of 326) still report zero markers, confirmed by inspection to be genuinely structure-less content (petition templates, explanatory prose), not remaining segmenter bugs. Mean text-coverage when markers are found: 85.7%. H2 is now testable on the actual corpus structure, not just a hoped-for one — the segmenter's real precision on true article boundaries (as opposed to marker-detection recall) still needs a labeled sample to measure, since marker_count and coverage_ratio are recall/coverage proxies, not precision measurements.

---

## H3 — Metadata-aware candidate pruning reduces resource use without recall loss

**Claim:** Using explicit metadata (jurisdiction, law_id, category, article-number-in-query) as a hard or soft pre-filter before dense/BM25 scoring reduces the candidate set the reranker must process (lower CPU/RAM/latency) without reducing Recall@K, because most queries are not actually ambiguous about which law/category they concern.

**Falsified if:** pruning measurably drops Recall@K for a non-trivial fraction of queries (i.e. category/law-name metadata is unreliable or the query's true relevant law disagrees with its apparent surface category), meaning metadata is a signal, not a filter.

**Experiment:** Experiment B (Metadata-aware retrieval) from the Dataflare assessment, explicitly scoped as *"metadata as explicit features/filters, not a substitute for semantic relevance"* — the assessment doc itself already warns against over-trusting this, which this hypothesis takes seriously by requiring the falsification check above before pruning is adopted as a default.

**Primary metric:** Recall@K delta (pruned vs unpruned) and resource delta (CPU/RAM/latency), on the reference hardware target (Quadro M2200 per ARCHITECTURE_CONTRACT.md).

**Minimum evidence bar:** resource measurement must be on the named reference hardware, not a cloud instance — RESOURCE_RELIABILITY_SPEC.md already flags GPU numbers on the M2200 as an outstanding gap; this experiment cannot claim a resource win without closing that gap first.

---

## H4 — Evidence-span retrieval improves groundedness more than scaling the LLM

**Claim:** For a fixed generation model, narrowing retrieved evidence from article-level chunks down to the specific supporting passage/span (Experiment D-style "long-document evidence extraction") improves groundedness/faithfulness (does the generated answer's claims actually appear in the cited evidence) more than upgrading to a larger LLM with the same article-level evidence.

**Falsified if:** a larger LLM with coarse article-level evidence produces equal or better groundedness scores than the current LLM with span-level evidence, meaning the bottleneck is generation capability, not evidence precision.

**Experiment:** Experiment D (Long-document evidence extraction) from the Dataflare assessment, extended with a groundedness metric. Requires: (a) a way to measure groundedness — entailment/support checking between generated claims and cited spans, not yet built (EVALUATION_SYSTEM_SPEC.md's evaluation-level L9/entailment work); (b) a controlled comparison holding the LLM fixed while varying evidence granularity, and a second run holding evidence granularity fixed while varying LLM size/model.

**Real-data update (2026-08-28):** full-corpus archaeology on the real Dataflare parquet found 86.7% of records (2,110 of 2,434) are Court of Cassation case-ruling excerpts, not statute text, with 94.8% clean citation extraction (appeal number + year + technical office + date — see `src/legal_ai/ingestion/case_citation_extraction.py`, DR-021). This materially strengthens H4's testability: case-citation-grounded evidence spans are exactly the kind of independently verifiable precedent unit groundedness measurement needs, and this is now a measured property of the actual corpus, not an aspiration.

**Primary metric:** groundedness/faithfulness score (claims-supported-by-cited-evidence rate), not just retrieval Recall@K — this hypothesis is explicitly about generation quality, not retrieval quality, and must not be scored with retrieval metrics alone.

**Minimum evidence bar:** requires the entailment/groundedness evaluator to exist first; this is the least immediately testable of the five hypotheses and should not be attempted before H1–H3 have usable infrastructure.

---

## H5 — Domain adaptation is not the best investment until proven necessary by benchmark

**Claim:** Continued pretraining / SFT / domain adaptation of the base LLM on the Egyptian legal corpus will not outperform retrieval/evidence-pipeline improvements (H1–H4) as the next investment, until a specific, measured failure mode is identified that retrieval, evidence selection, prompting, or model routing cannot reasonably address.

**Falsified if:** after H1–H4 are implemented and measured, a benchmark failure category persists (e.g., legal reasoning that requires synthesizing rules across articles in a way no retrieval/evidence design can present cleanly enough for the base LLM to use) — at that point domain adaptation becomes the justified next step, not a default first step.

**This is a governance hypothesis, not a retrieval experiment.** It is already encoded as a hard rule in `docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md`'s "Training recommendation" section and in this project's Stage discipline (fine-tuning is out of scope through at least Stage 1–3). H5 is confirmed by construction unless and until H1–H4 experiments are run and a residual failure mode is documented — there is no separate experiment for H5; it is falsified specifically by the failure-mode evidence described above, and only that evidence.

**Minimum evidence bar for overturning H5 (i.e., justifying domain adaptation):** a written failure-mode analysis showing (a) the failure persists after best-effort H1–H4 implementations, (b) the failure is attributable to the base LLM's legal knowledge/reasoning rather than evidence quality, and (c) project-owner sign-off, per DR precedent (training-role license gate in `dataset_manifest.py` already encodes "no training without an explicit, checked gate" as a pattern).

---

## Dependency graph

```text
H2 (article-aware chunking)
   ↓ (produces article-level structure)
H1 (hierarchical > flat retrieval)
   ↓ (produces evidence-selection substrate)
H4 (evidence-span > bigger LLM) ←── requires groundedness evaluator (separate build)
   ↓
H5 (domain adaptation only if H1–H4 insufficient) ←── governance gate, not an experiment

H3 (metadata pruning) — independent, can run in parallel with H1/H2,
                          but requires resource measurement on real M2200 hardware.
```

H2 must be validated on real Dataflare text before H1 can be tested meaningfully — the segmenter's own precision/recall is a prerequisite, not an assumption.

## What "we found the moat" actually requires

If H1–H4 are confirmed under their stated minimum evidence bars, the project has evidence — not marketing language — for the claim that legal-structure-aware retrieval is a real, measured advantage over generic RAG. That evidentiary bar is what turns "we built a legal chatbot" into "we can show why retrieval trained on legal structure outperforms retrieval that ignores it, and by how much, under what resource budget." Until each hypothesis clears its stated bar, it must be discussed as an open hypothesis, not a project claim — including in product/marketing material.
