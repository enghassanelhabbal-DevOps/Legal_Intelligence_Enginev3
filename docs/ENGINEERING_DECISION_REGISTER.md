# Engineering Decision Register

This register records durable architectural decisions. New decisions should be added rather than silently rewriting history.

## DR-001 — v3 is the canonical foundation

Status: accepted.

Decision: Continue from `Legal_Intelligence_Enginev3`; do not rewrite from zero.

Reason: v3 already contains the strongest known modular retrieval, API lifecycle, LLM adapter, evaluation, DVC, Docker, and CI foundation.

Consequence: legacy duplicate paths become migration debt, not justification for a wholesale rewrite.

## DR-002 — Evidence-first architecture

Status: accepted.

Decision: Retrieval and evidence precede generation. The LLM is not the source of legal truth.

Consequence: every answer path must expose evidence/provenance and cannot bypass evidence validation.

## DR-003 — Knowledge updates do not normally require model retraining

Status: accepted.

Decision: Current legal updates enter through versioned ingestion, indexing, and knowledge releases.

Consequence: the base LLM can remain replaceable and knowledge remains independently auditable.

## DR-004 — Historical 0.835 retrieval score is not a trusted protected baseline

Status: accepted.

Decision: Treat the historical 0.835 hybrid figure as unverified until a reproducible harness and artifact lineage are recovered.

Consequence: current CI smoke metrics remain regression guards only; a full production-pipeline benchmark must be established.

## DR-005 — Retrieval and legal understanding are separate measurements

Status: accepted.

Decision: Never infer legal understanding from retrieval Recall/MRR.

Consequence: expert-labeled reasoning, entailment, temporal, jurisdiction, and abstention benchmarks are required.

## DR-006 — Resource efficiency is a product requirement

Status: accepted.

Decision: Support CPU-only, constrained GPU, normal GPU, and remote inference through one domain contract.

Consequence: bounded workers, batching, model residency, and graceful degradation are first-class concerns.

## DR-007 — Failure learning is controlled, not self-modifying

Status: accepted.

Decision: Failures can create telemetry and regression cases, but runtime cannot silently modify code, prompts, thresholds, knowledge, or model weights.

Consequence: improvements enter through reviewed releases.

## DR-008 — Claude is an implementation and adversarial-review partner

Status: accepted.

Decision: Substantial stages use Claude for code implementation/review, while the review step is separated from any authorized production change.

Consequence: review findings must be resolved and re-tested before merge.

## DR-009 — Egypt first, jurisdiction packs later

Status: accepted.

Decision: Initial product wedge targets Egyptian legal research. Additional jurisdictions are explicit versioned packs.

Consequence: data, evaluation, authority semantics, and temporal coverage remain jurisdiction-scoped.

## DR-010 — No premature distributed architecture

Status: accepted.

Decision: Scale single-node correctness first, then efficiency, reliability, stateless horizontal API, and only then distributed components if measured demand requires them.

Consequence: Kubernetes/microservices/distributed vector search are not first-stage requirements.

## DR-011 — Human/legal expert validation remains necessary

Status: accepted.

Decision: Legal-domain semantics such as authority, ambiguity, amendments, conflicts, and expert gold answers require domain review where model-based validation is insufficient.

Consequence: the benchmark process must support expert annotation and disagreement tracking.

## DR-012 — No claim without reproducible evidence

Status: accepted.

Decision: Accuracy, latency, memory, throughput, cost, and reliability claims require reproducible reports.

Consequence: benchmark artifacts and experiment manifests become part of release evidence.
