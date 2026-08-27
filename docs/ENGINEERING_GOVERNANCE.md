# Engineering Governance

## Mission

Build a resource-efficient, jurisdiction-aware, evidence-first Legal Intelligence Platform that is measurable, fault-tolerant, reproducible, and extensible across hardware classes.

## Non-negotiable principles

1. Evidence before generation: legal claims must be traceable to retrieved evidence.
2. Knowledge is separate from model weights: legal updates enter through ingestion/versioned knowledge releases, not routine LLM retraining.
3. No benchmark inflation: never compare numbers produced by different evaluation definitions as if they were equivalent.
4. No data leakage: train, validation, and test splits must be constructed before model/index tuning and must respect legal-document, law, version, and query-family boundaries.
5. No production self-modification: runtime failures may create learning signals, regression cases, or configuration recommendations, but cannot silently mutate production models/indexes/configuration.
6. Fail closed on legal uncertainty: insufficient evidence, conflicting authorities, jurisdiction mismatch, or temporal ambiguity must produce explicit warnings/abstention.
7. Resource-aware execution: every expensive stage must have a bounded resource budget and a fallback/degradation path.
8. Reproducibility: dataset, knowledge release, model, retriever, reranker, configuration, and code versions must be recorded with every benchmark and material query trace.
9. Incremental change: preserve working baselines and make one logical change at a time.
10. Security by default: secrets, uploaded legal documents, prompts, retrieved text, and external sources are untrusted inputs.

## Quality gates

### Gate A — Data quality

- schema validation
- provenance/source authority
- content hash
- duplicate detection
- metadata completeness
- jurisdiction validation
- legal version/effective-date validation
- language/encoding checks
- licensing/provenance record
- train/validation/test leakage checks

### Gate B — Retrieval quality

Minimum tracked metrics:

- MRR
- Recall@1/3/5/10
- Full Recall@1/3/5/10 for multi-evidence queries
- Precision@k where labels permit
- nDCG@k where graded relevance exists
- candidate recall before reranking
- dense preservation rate
- latency p50/p95
- peak RAM/VRAM

### Gate C — Legal understanding

Separate from retrieval. Track:

- issue identification
- rule identification
- exception identification
- fact-to-rule matching
- multi-article reasoning
- temporal validity
- jurisdiction validity
- contradiction detection
- abstention/insufficient-evidence quality

### Gate D — Grounded generation

Track:

- citation validity
- citation completeness
- evidence coverage
- unsupported-claim rate
- contradiction rate
- structured-output validity
- answer usefulness judged by human reviewers

### Gate E — Reliability

- startup/readiness correctness
- retry behavior
- bounded concurrency
- graceful degradation
- model/index lifecycle
- deterministic failure classification
- recovery success rate
- no request-level heavy model reloads

### Gate F — Security

- no tracked secrets
- upload validation
- prompt injection defenses
- path traversal defenses
- rate limits
- audit trail
- safe error messages
- tenant/data isolation before multi-user deployment

## Failure Learning Loop

Runtime failures are normalized into a versioned failure record:

`failure -> classify -> contain -> recover/degrade -> record -> regression case -> evaluate -> fix -> release`

Failure records must include at least:

- timestamp
- request/query id
- failure class
- stage
- jurisdiction
- knowledge release
- dataset/retriever/reranker/model version
- hardware profile
- resource state
- recovery action
- outcome

No automatic production code/model/config mutation is allowed from this loop.

## Hardware tiers

The system must support a common execution contract across:

- CPU-only low-memory laptop
- CPU + 4 GB-class GPU
- modern workstation GPU
- cloud GPU
- remote LLM/API-only mode

Feature availability may degrade by tier, but correctness and explicit status reporting must remain stable.

## Evaluation datasets

Maintain independent dataset roles:

- knowledge corpus: authoritative legal source data
- retrieval benchmark: human/curator-labeled relevance
- reranker benchmark: query-document graded relevance/pairwise preference
- reasoning benchmark: question + evidence + expected legal analysis
- grounded-generation benchmark: evidence + expected supported answer/citations
- adversarial benchmark: ambiguity, prompt injection, temporal conflicts, jurisdiction confusion, insufficient evidence

A dataset may serve more than one role only when explicitly documented and leakage-tested.

## Legal domain policy

The first production jurisdiction is Egypt. MENA expansion is additive and jurisdiction-isolated. Cross-jurisdiction answers require explicit scope and separate evidence pools.

Arabic support must cover:

- Modern Standard Arabic
- Egyptian colloquial user phrasing
- spelling variation
- Arabic/English code-switching
- article references and legal abbreviations

Normalization is retrieval-oriented and must never destroy source text.
