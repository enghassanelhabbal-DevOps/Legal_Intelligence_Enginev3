# Evaluation System Specification

## 1. Objective

Create a reproducible evaluation system that can answer five separate questions:

1. Did retrieval find the right evidence?
2. Did ranking put the useful evidence first?
3. Did the system understand the legal problem?
4. Did the final answer remain supported by evidence?
5. Did the system remain efficient and reliable?

No single score may represent all five.

## 2. Evaluation hierarchy

```text
Data quality
  -> Retrieval
  -> Reranking
  -> Evidence support
  -> Legal understanding
  -> Grounded generation
  -> Operational quality
```

Each layer must be testable independently and end-to-end.

## 3. Benchmark tiers

### Tier 0 — Unit/regression
Fast deterministic tests. No network and no large model downloads.

### Tier 1 — Smoke retrieval
Current corpus smoke test. Purpose: catch gross regressions only.

### Tier 2 — Real retrieval benchmark
Expert/user-style queries with human- or expert-labeled relevant evidence sets.

### Tier 3 — Legal understanding benchmark
Gold issue, rules, exceptions, fact-to-rule mappings, temporal/jurisdiction semantics.

### Tier 4 — End-to-end grounded answer benchmark
Question -> retrieval -> evidence -> generation -> claim support.

### Tier 5 — Adversarial benchmark
Ambiguity, conflicts, temporal changes, jurisdiction look-alikes, prompt injection, insufficient evidence, noisy Arabic, and malformed documents.

## 4. Retrieval metrics

Required:

- MRR;
- Recall@1/3/5/10;
- candidate recall before reranking;
- evidence-set coverage;
- Full Recall@K for multi-evidence cases;
- missing-essential-evidence rate.

Optional as scale grows:
- nDCG@K;
- MAP;
- precision@K.

## 5. Reranker metrics

Measure ranking quality both absolutely and as delta from candidate generation.

Record:

```text
candidate recall
MRR / Recall@K
rerank delta
latency
CPU/RAM/VRAM
```

A reranker that increases ranking quality but destroys practical latency must be evaluated as a trade-off, not automatically accepted.

## 6. Arabic robustness matrix

Each benchmark category should have paired variants where applicable:

```text
canonical Arabic
orthographic variant
no diacritics
with diacritics
spelling noise
punctuation variation
article-number variation
formal paraphrase
colloquial formulation
Arabic/English mixed formulation
```

Measure the change in retrieval and answer correctness across variants.

## 7. Legal understanding metrics

For expert-labeled cases measure:

- issue identification accuracy;
- rule identification accuracy;
- condition recognition;
- exception recognition;
- fact extraction relevance;
- fact-to-rule application;
- multi-article synthesis;
- temporal rule selection;
- jurisdiction selection;
- conflict identification.

## 8. Evidence support metrics

For each material generated claim:

```text
supported
partially_supported
contradicted
unsupported
```

Report:

- support rate;
- unsupported claim rate;
- contradiction rate;
- citation validity;
- citation coverage;
- evidence sufficiency accuracy.

## 9. Abstention metrics

Build both answerable and unanswerable cases.

Measure:

- abstention precision;
- abstention recall;
- false-answer rate on insufficient evidence;
- over-abstention rate on answerable cases.

A safe system should not answer unsupported questions confidently.

## 10. Temporal and jurisdiction evaluation

Cases must include:

- current rule;
- historical rule;
- amendment boundary;
- repeal/supersession;
- same/similar rule in another jurisdiction;
- explicit jurisdiction comparison.

Metrics must capture both selection correctness and final-answer correctness.

## 11. Dataset leakage tests

Before a benchmark is considered valid, run:

- exact text overlap detection;
- normalized text overlap;
- duplicate ID detection;
- source-level overlap;
- law-level overlap;
- near-duplicate review where practical.

Benchmark contamination is a release blocker.

## 12. Experimental protocol

Every experiment has a manifest:

```text
experiment_id
commit
config
code version
model versions
knowledge release
dataset versions
seed
hardware profile
metrics
latency
resource measurements
result
accept/reject decision
```

No result is considered reproducible without this context.

## 13. Statistical discipline

For sufficiently large test sets:

- report sample size;
- report confidence intervals where practical;
- avoid overinterpreting tiny metric changes;
- compare per-category performance, not only aggregate means.

For small expert sets, report individual cases and qualitative error analysis.

## 14. Protected baseline policy

The historical `0.835` MRR hybrid figure is **unverified historical reference** until its original harness and data are reproducibly reconstructed.

The current BM25 self-retrieval CI baseline is a regression guard, not a legal-understanding benchmark.

The full production retrieval path must eventually have its own reproducible held-out benchmark.

## 15. Golden set

Maintain a small, human-reviewed golden set that covers:

- direct questions;
- paraphrases;
- multi-evidence cases;
- exceptions;
- temporal cases;
- jurisdiction cases;
- conflicts;
- insufficient evidence.

The golden set is protected and changed only through controlled review.

## 16. Release gates

A release should fail when:

- held-out retrieval regresses beyond approved tolerance;
- unsupported-claim rate increases beyond approved tolerance;
- temporal/jurisdiction correctness drops below threshold;
- critical security tests fail;
- severe resource limits are exceeded;
- new data contaminates evaluation;
- citation validation is bypassed.

Thresholds must be established from measured baseline data rather than invented upfront.
