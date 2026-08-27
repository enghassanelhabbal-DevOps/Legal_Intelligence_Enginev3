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

## DR-013 — Canonicalize Gemini generation backend

Status: accepted.

Decision: Gemini is a named remote LLM provider in the current production path and must be represented by a canonical `GeminiBackend` under `src/legal_ai/generation/backends/`, conforming to the shared generation adapter contract.

Current state: provider-specific Gemini behavior currently exists in root `app.py`, including model-variant fallback and bounded retry behavior. This is treated as technical debt and a second generation implementation, analogous to the previously identified retrieval duplication.

Migration rule:

```text
inventory current Gemini behavior
→ define adapter parity contract
→ implement GeminiBackend
→ add parity/failure/resource tests
→ route QueryService/GenerationManager through canonical backend
→ verify supported behavior and metrics
→ remove vendored Gemini implementation from app.py
→ repository-wide search confirms one active Gemini implementation
```

Provider/data-boundary policy: Gemini is an external trust boundary. The system must make the selected provider explicit and must not send data classified as disallowed for that provider. Provider credentials and sensitive payloads must not appear in logs, fixtures, or committed files.

Consequence: Gemini provider changes belong to the generation layer and its configuration; retrieval, evidence, API, and UI must remain provider-agnostic.

## DR-014 — Root app.py is not a permanent business-logic boundary

Status: accepted.

Decision: Deployment convenience, including single-process Streamlit hosting constraints, does not justify active duplicate retrieval or generation business logic in root `app.py`.

Decision rule: Any new capability first added to `app.py` for deployment convenience is presumptively a duplication violation unless it is presentation/transport-only or has an explicit, versioned migration path into the canonical `src/legal_ai` layer.

Consequence: Stage 3 must remove retrieval and generation duplication and preserve only thin entrypoint behavior where necessary.

## DR-015 — Stage 4 owns the full production retrieval benchmark

Status: accepted.

Decision: The reproducible benchmark for the exact dense + lexical + reranker production retrieval path is a Stage 4 deliverable and the gate for later retrieval optimization claims.

Consequence: no full-stack retrieval optimization claim may rely only on the current BM25 smoke gate or the unverified historical 0.835 figure.

## DR-016 — Security controls are staged by risk

Status: accepted.

Decision: Security controls are implemented according to execution risk and product maturity rather than as one undifferentiated enterprise backlog.

Consequence: baseline secrets/data/file/prompt boundaries begin in early stages; tenant isolation, data residency, and enterprise governance are introduced when the commercial platform requires them.
