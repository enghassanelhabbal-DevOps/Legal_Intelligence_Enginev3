# ARCHITECTURE CONTRACT V4 — DRAFT

> **Status:** Draft for human + Claude review. This file is not authoritative until explicitly approved and promoted to `ARCHITECTURE_CONTRACT.md`.
>
> **Purpose:** Align architecture, product intent, legal-domain behavior, evaluation, resource efficiency, reliability, security, and future scalability before substantial implementation work begins.

---

## 1. Mission and product identity

Build an **evidence-first, jurisdiction-aware, version-aware, resource-efficient Legal Intelligence Platform** for Arabic and emerging legal systems, starting with **Egypt**.

The system is not a generic legal chatbot and must not be architected around a chat interface. The durable product value is:

- trustworthy legal retrieval;
- complete and correctly ranked evidence sets;
- legal-context and query understanding;
- jurisdiction correctness;
- temporal/version correctness;
- evidence-supported legal reasoning;
- explicit uncertainty and safe abstention;
- auditable provenance and citations;
- measurable reliability;
- measurable CPU/RAM/VRAM/latency/throughput/cost efficiency;
- portability from constrained local hardware to cloud/enterprise deployment.

The technical core should be capable of evolving from a single-node engine into an API/SaaS/enterprise platform without rewriting legal domain contracts.

### Product wedge

The first practical product wedge is:

**Egyptian legal research + evidence reports for professional users.**

Potential expansion order:

```text
Egypt
  -> Egypt temporal/amendment intelligence
  -> Egypt case/fact-to-rule analysis
  -> GCC/MENA jurisdiction packs
  -> multi-jurisdiction legal intelligence
  -> API / SaaS
  -> enterprise / private deployment
```

Expansion is explicit and evidence-driven. A new jurisdiction is not enabled merely by adding documents to the same undifferentiated corpus.

---

## 2. Core principles

### 2.1 Knowledge is independent from model weights

Legal knowledge is a first-class system asset. Source text, authority, provenance, versions, amendments, releases, indexes, and evaluation assets are independently managed from the LLM.

Ordinary legal updates should normally enter through ingestion, versioning, indexing, and a controlled knowledge release. Retraining the base LLM is not the default mechanism for updating law.

### 2.2 Evidence before generation

Generation is downstream from retrieval and evidence validation.

The LLM is a replaceable reasoning/generation component. It is not the legal authority.

### 2.3 Measured engineering

No claim of improved accuracy, latency, memory use, throughput, reliability, or cost is valid without reproducible measurement.

### 2.4 Safe uncertainty

When evidence is missing, ambiguous, contradictory, stale, or outside the requested jurisdiction/time scope, the system must surface that condition and may abstain.

### 2.5 No silent semantic changes

Raw source material must be preserved. Search normalization is a derived representation. Jurisdiction, version, amendment, repeal, supersession, and provenance changes must remain explicit.

### 2.6 No production self-modification

Runtime failures may produce telemetry, regression cases, and recommended improvements, but may not silently modify production code, prompts, thresholds, knowledge, or model weights.

---

## 3. Canonical architecture

The system has a **Knowledge Plane**, an **Intelligence Plane**, and a cross-cutting **Evaluation / Reliability / Resource layer**.

```text
                                  LEGAL INTELLIGENCE PLATFORM
                                             |
                      +----------------------+----------------------+
                      |                                             |
               KNOWLEDGE PLANE                              INTELLIGENCE PLANE
                      |                                             |
     Sources -> Provenance -> Parsing -> Structure            User Query
                      |                                             |
              Normalization / Metadata                   Query Understanding
                      |                                             |
        Version / Amendment / Authority                   Jurisdiction / Time
                      |                                             |
              Release Candidate                          Retrieval Planning
                      |                                             |
             Index Generation                         Dense + Lexical Retrieval
                      |                                             |
              Evaluation Gate                            Candidate Union/Filter
                      |                                             |
               Atomic Publish                               Reranking
                                                                    |
                                                             Evidence Selection
                                                                    |
                                                          Support / Conflict Check
                                                                    |
                                                      Grounded Reasoning / Generation
                                                                    |
                                                       Verification / Abstention
                                                                    |
                                              Structured Answer + Citations + Warnings
                                                                    |
                      +---------------------------------------------+
                      |
             Telemetry / Evaluation / Resource / Cost / Failure Intelligence
```

### Canonical request flow

```text
User/API/UI
    -> QueryRequest
    -> Query Understanding
    -> Retrieval Plan
    -> Dense + Lexical Retrieval
    -> Metadata / Jurisdiction / Temporal Filtering
    -> Candidate Union
    -> Reranking
    -> EvidenceSet Construction
    -> Evidence Support / Conflict Checks
    -> Grounded Generation
    -> Citation Validation
    -> Abstention / Warning Decision
    -> Answer
    -> Telemetry
```

### Hard dependency direction

```text
API/UI -> services -> retrieval -> reranking -> evidence -> generation
                         ^
                         |
                knowledge <- ingestion

Evaluation observes and evaluates all measurable stages.
Core runtime/resource/fault infrastructure is cross-cutting but must not
be duplicated inside each backend.
```

Rules:

- API/UI contain transport or presentation concerns only.
- Services orchestrate; they do not reimplement retrieval, prompting, or data parsing.
- Retrieval owns dense, lexical, hybrid candidate generation and retrieval filters.
- Reranking owns candidate scoring.
- Evidence owns evidence-set construction, context shaping, support/citation validation and conflict signals.
- Generation owns LLM interfaces and backend adapters.
- Knowledge owns legal entities, authority, provenance, versions and releases.
- Ingestion owns parsing, normalization, validation, hashing, deduplication and metadata extraction.
- Evaluation owns datasets, metrics, benchmarks, leakage controls and regression gates.
- Core owns contracts, configuration, runtime/resource policy, failure taxonomy and logging.
- No duplicate business logic between layers.

---

## 4. Canonical domain model

The minimum legal identity must be rich enough to support real legal research rather than simple text search.

### LegalDocument minimum fields

```text
 document_id
 jurisdiction
 country
 language
 legal_system
 law_id
 law_name
 law_type
 article_id
 section
 chapter
 paragraph_id
 raw_text
 normalized_text
 embedding_text
 source
 source_url
 source_authority
 publication_date
 effective_from
 effective_to
 amendment_date
 version_id
 previous_version_id
 next_version_id
 status
 page
 citation
 content_hash
 document_hash
```

Missing metadata must remain explicit (`null`, `unknown`, or equivalent controlled state) and trigger a data-quality signal where relevant. Never fabricate legal metadata.

### First-class contracts

The architecture should evolve toward explicit contracts for at least:

```text
LegalDocument
LegalVersion
LegalCitation
LegalSource
RetrievalHit
EvidenceItem
EvidenceSet
QueryRequest
QueryUnderstanding
RetrievalPlan
QueryResponse
Answer
EvaluationCase
EvaluationResult
KnowledgeRelease
ModelInfo
TimingInfo
ResourceInfo
FailureEvent
```

The exact Python implementation may evolve, but contract responsibilities must remain stable.

---

## 5. Knowledge lifecycle

Every new legal source or update must be processed through a controlled lifecycle.

```text
raw source
  |
  v
provenance / license / authority check
  |
  v
parse
  |
  v
schema validation
  |
  v
raw-text preservation
  |
  v
Arabic/search normalization
  |
  v
legal structure extraction
  |
  v
metadata enrichment
  |
  v
deduplication / near-duplicate detection
  |
  v
version / amendment / repeal / supersession analysis
  |
  v
knowledge release candidate
  |
  v
index generation
  |
  v
evaluation gate
  |
  v
atomic publish
```

Knowledge releases must be:

- deterministic;
- versioned;
- identifiable;
- auditable;
- reproducible;
- rollbackable.

A query must resolve which knowledge release and legal version set it used.

### Knowledge authority

The system should distinguish at minimum:

- primary official/legal sources;
- judicial decisions;
- regulatory/administrative sources;
- secondary legal sources;
- user-provided/private materials.

Authority level must be represented in metadata and must not be inferred silently from text.

---

## 6. Temporal and jurisdiction semantics

Temporal and jurisdiction correctness are core correctness properties, not optional filters.

### Temporal requirements

The system must support concepts such as:

```text
published_at
 effective_from
 effective_to
 amended_at
 repealed_at
 superseded_by
 supersedes
 version_id
```

Questions may explicitly refer to a date, or the product may operate under a selected legal-as-of date.

The system must not silently mix historical and current law.

### Jurisdiction requirements

Every knowledge item has an explicit jurisdiction. Cross-jurisdiction retrieval is disabled by default unless the request explicitly requires comparison or the system is operating in a comparison mode.

Examples:

```text
EG != SA != AE != QA
```

Similar wording between jurisdictions must not be treated as equivalence.

---

## 7. Query understanding

Before retrieval, the system should progressively support a structured query interpretation layer.

```text
language
jurisdiction
country/legal system
legal domain
requested or reference date
query intent
question type
candidate authority types
single-hop / multi-hop
required evidence types
risk / ambiguity flags
```

Examples of query types:

- article lookup;
- rule explanation;
- condition/exception question;
- fact-to-rule application;
- multi-article synthesis;
- temporal/historical question;
- jurisdiction comparison;
- contradiction/conflict question;
- evidence sufficiency question.

Query understanding may recommend a retrieval plan, but must not invent legal facts or silently override explicit user constraints.

---

## 8. Retrieval architecture

The current v3 retrieval baseline is protected as a regression reference, not as evidence of final product quality.

### Default retrieval flow

```text
query
  |
query normalization / structured understanding
  |
+---------------------------+
|                           |
Dense retrieval        Lexical retrieval
|                           |
+-------------+-------------+
              |
      dense-preserving union
              |
  jurisdiction / temporal / metadata filters
              |
          reranking
              |
       evidence selection
```

### Protected baseline

```text
MRR        = 0.835
Recall@1   = 0.75
Recall@3   = 0.90
Recall@5   = 0.95
Recall@10  = 1.00
```

These numbers are **regression references only**.

### Multi-evidence objective

For questions needing multiple authorities, report:

- Full Recall@K;
- evidence-set coverage;
- missing-evidence rate;
- candidate recall before reranking;
- final evidence recall after reranking.

A result that retrieves one relevant article while omitting an essential companion article is not a complete retrieval success.

### Experiment rules

Every retrieval/reranker change must report:

- exact dataset/evaluation version;
- baseline configuration;
- candidate-generation configuration;
- ranking configuration;
- before metrics;
- after metrics;
- per-category metric deltas;
- latency deltas;
- CPU/RAM/VRAM impact;
- throughput impact;
- failure/regression observations.

Do not replace the current fusion strategy because another algorithm is fashionable. Replace it only after a controlled experiment demonstrates a justified improvement or resolves a documented limitation.

---

## 9. Arabic legal-language intelligence

Arabic normalization is a retrieval representation, not an authority replacement.

The system must preserve original legal wording while supporting configurable normalization and robust user-query handling.

Evaluation should cover:

- alef variants;
- ya/alif-maqsura variation;
- diacritics;
- tatweel;
- punctuation variation;
- whitespace/noise;
- common spelling variation;
- Arabic/English mixed queries;
- article-number formats;
- common legal abbreviations;
- legal terminology and synonyms;
- paraphrased formal Arabic;
- realistic colloquial user phrasing where appropriate.

The engine must distinguish:

```text
retrieval robustness
        !=
legal understanding
```

A system that finds the right article for a near-copy query has not proven legal reasoning capability.

---

## 10. Legal understanding architecture

Legal understanding is evaluated separately from retrieval.

The minimum target capabilities are:

1. Issue identification.
2. Applicable rule identification.
3. Condition detection.
4. Exception detection.
5. Fact extraction relevant to the legal rule.
6. Fact-to-rule application.
7. Multi-article synthesis.
8. Temporal rule selection.
9. Jurisdiction selection.
10. Conflict identification.
11. Evidence sufficiency assessment.
12. Safe abstention.

A legal answer should be treated as a structured reasoning result over validated evidence, not free-form model prose.

---

## 11. Evidence architecture

Evidence is a first-class object.

Each `EvidenceItem` should retain, where available:

```text
evidence_id
document_id
law_id
law_name
article_id
jurisdiction
version_id
source
source_authority
citation
text_span
retrieval_score
reranker_score
support_role
conflict_state
quality_flags
```

An `EvidenceSet` represents the complete evidence selected for one answer.

### Claim-to-evidence mapping

Every material generated claim must map to one or more evidence identifiers.

```text
Claim C1 -> Evidence E1, E3
Claim C2 -> Evidence E4
Claim C3 -> unsupported -> failure / abstention
```

Citation validation must be an enforced pipeline gate, not merely a warning helper.

### Support semantics

The product should eventually distinguish:

- directly supports;
- partially supports;
- contradicts;
- context-only;
- insufficient;
- outdated;
- conflicting authority.

---

## 12. Grounded generation and reasoning

Generation receives a bounded structured evidence context.

The prompt contract must clearly separate:

```text
SYSTEM INSTRUCTIONS
USER REQUEST
LEGAL EVIDENCE
OUTPUT SCHEMA
```

Retrieved text is untrusted content and may not override higher-priority instructions.

The generation layer must:

- support stable structured output;
- cite evidence identifiers;
- expose warnings and uncertainty;
- avoid unsupported legal claims;
- support abstention;
- distinguish retrieved law from model interpretation;
- avoid exposing hidden chain-of-thought.

The product may return concise reasoning summaries such as:

```text
Rule identified: ...
Relevant condition: ...
Application summary: ...
Evidence: E1, E2
Uncertainty: ...
```

It must not expose hidden internal chain-of-thought.

---

## 13. Abstention and safety model

The system must have an explicit decision path for insufficient evidence.

```text
Retrieve
  |
Evidence sufficiency check
  |
  +---- sufficient ----> reason / generate
  |
  +---- ambiguous -----> warn / narrow / ask for missing constraint
  |
  +---- contradictory --> surface conflict
  |
  +---- outdated -------> warn / select correct temporal version
  |
  +---- insufficient ---> abstain
```

Abstention quality must be evaluated, not treated as an error in every case.

---

## 14. Evaluation architecture

Evaluation is a first-class subsystem and release gate.

Maintain independent evaluation tracks.

### A. Retrieval relevance

- MRR;
- Recall@K;
- candidate recall;
- latency.

### B. Multi-evidence retrieval

- Full Recall@K;
- evidence-set coverage;
- missing-evidence rate.

### C. Reranking

- ranking quality;
- contribution relative to candidate generation;
- latency/resource cost.

### D. Arabic robustness

- orthographic robustness;
- paraphrase;
- spelling variation;
- terminology;
- mixed-language;
- article-reference robustness.

### E. Legal understanding

- issue identification;
- rule identification;
- exception handling;
- fact-to-rule application;
- multi-article synthesis.

### F. Entailment/support

- evidence support rate;
- unsupported claim rate;
- contradiction rate.

### G. Grounded generation

- citation validity;
- citation coverage;
- unsupported-claim rate;
- evidence sufficiency handling;
- abstention precision/recall where applicable.

### H. Temporal correctness

- historical rule selection;
- amendment handling;
- repeal/supersession handling.

### I. Jurisdiction correctness

- jurisdiction selection accuracy;
- cross-jurisdiction confusion rate.

### J. Reliability

- failure rate;
- recovery success rate;
- degraded-mode success;
- restart safety;
- reproducibility.

### K. Efficiency

- CPU utilization;
- RAM peak;
- VRAM peak;
- latency;
- throughput;
- token usage;
- estimated cost per query.

---

## 15. Evaluation dataset design

The final evaluation system must contain multiple dataset roles.

```text
knowledge corpus
retrieval tuning/training
reranker tuning/training
reasoning/SFT
validation
held-out test
challenge/adversarial
benchmark-only
```

The current self-retrieval smoke set is **regression guard only**.

The final benchmark must include realistic user-style queries and expert/human labeling where possible.

Required benchmark categories include:

```text
Direct lookup
Paraphrase
Colloquial user phrasing
Multi-article
Fact pattern
Exception
Temporal
Jurisdiction confusion
Contradiction
Insufficient evidence
Adversarial / prompt injection
```

### Leakage control

Prefer source-level, law-level, or version-aware separation over naive random record splitting when legal text overlaps.

No held-out benchmark may be used for:

- training;
- fine-tuning;
- prompt selection;
- threshold tuning;
- model selection;
- retrieval parameter optimization.

Every dataset entering the platform must first be profiled.

---

## 16. Dataset intake protocol

New datasets must pass:

```text
Dataset
  -> provenance
  -> license/usage-rights
  -> schema inspection
  -> language detection
  -> jurisdiction detection
  -> authority classification
  -> legal-time coverage
  -> duplicate/near-duplicate analysis
  -> annotation quality analysis
  -> contamination/leakage analysis
  -> task classification
  -> split design
  -> approval
```

Dataset size is not a quality metric.

A dataset may be suitable for one task and unsuitable for another.

For example:

```text
legal articles
    -> knowledge corpus / retrieval
QA pairs
    -> retrieval + reasoning evaluation
IR pairs
    -> retriever/reranker tuning
IRAC answers
    -> reasoning evaluation / possible SFT
adversarial examples
    -> challenge benchmark
```

---

## 17. Resource architecture

Resource efficiency is a product requirement.

The engine must adapt execution to available hardware rather than assuming one machine class.

```text
Hardware Discovery
       |
       v
Resource Budget
       |
       v
Execution Profile
       |
       v
Bounded Workers / Queue / Batch
       |
       v
Model Placement
       |
       v
Adaptive Execution
       |
       v
Telemetry
```

### Required profiles

- `cpu-minimal`;
- `balanced`;
- `accelerated`;
- `remote-llm`.

### Rules

- GPU is optional for portable core operation.
- FAISS/BM25 remain CPU-first where appropriate.
- Worker counts must be bounded.
- Queue sizes must be bounded.
- Batch sizes must be bounded and configurable.
- Memory pressure must influence execution when safe.
- Large model co-residency must be avoided on constrained GPUs.
- Heavy models should be offloaded/unloaded when appropriate.
- Request-time model/index rebuilds are prohibited.
- Unbounded retries are prohibited.
- Parallelism is increased only when measured workload justifies it.

### Target hardware

The Quadro M2200 4 GB / Compute Capability 5.2 environment is a development and stress target, not an architectural ceiling.

Do not assume Tensor Cores, FP8, or a specific GPU architecture.

---

## 18. Fault intelligence

The engine must treat failures as controlled system events.

```text
Failure
  |
Classify
  |
Contain
  |
Recover / Degrade
  |
Record fingerprint
  |
Regression / Evaluation case
  |
Fix
  |
Benchmark
  |
Release
```

### Failure categories

At minimum:

- invalid input;
- malformed legal document;
- provenance/metadata failure;
- corrupted artifact;
- missing index;
- model load failure;
- OOM;
- timeout;
- backend/API failure;
- dependency incompatibility;
- retrieval miss;
- evidence insufficiency;
- citation mismatch;
- temporal conflict;
- jurisdiction conflict;
- unexpected internal exception.

### FailureEvent

A failure record should capture, where safe:

```text
failure_id
request_id
operation
software_version
model_version
retriever_version
knowledge_release
dataset/evaluation version
hardware/resource profile
error category
error fingerprint
recovery action
recovery outcome
latency/resource context
```

Sensitive content should not be stored unnecessarily.

### Recovery requirements

Recovery strategies must be:

- deterministic;
- bounded;
- observable;
- reversible;
- safe for legal-data integrity.

Example:

```text
GPU OOM
  -> reduce batch
  -> retry once
  -> if still failing, offload/degrade
  -> if still failing, return controlled failure
```

Do not hide an outage behind infinite retries.

---

## 19. Failure-driven learning

Runtime failures may produce new evaluation cases.

Example:

```text
Production / staging failure
        |
        v
failure fingerprint
        |
        v
sanitized regression case
        |
        v
challenge benchmark
        |
        v
future releases must pass it
```

The system may recommend fixes, but runtime behavior must not self-edit production logic.

This distinction is essential:

```text
learning from failures = YES
uncontrolled self-modification = NO
```

---

## 20. Observability

Every important query or benchmark run should be traceable.

Track, where applicable:

```text
request_id
query_id
knowledge_release
retriever_version
reranker_version
model/backend
execution_profile
stage timings
CPU signals
RAM signals
VRAM signals
warnings
errors
recovery action
input/evaluation dataset version
```

Instrumentation must remain lightweight on constrained hardware.

The architecture should remain compatible with common metrics/tracing systems but must not force heavyweight observability dependencies into minimal deployments without justification.

---

## 21. Security

Treat all of the following as untrusted:

- user queries;
- uploaded legal documents;
- retrieved text;
- external sources/connectors;
- model outputs;
- dataset content.

Required controls progressively include:

- strict schema validation;
- input size limits;
- safe file paths;
- MIME/type validation;
- provenance checks;
- prompt-injection defenses;
- authentication;
- authorization boundaries;
- rate limiting;
- secrets outside source control;
- structured audit events;
- tenant isolation for future enterprise operation.

No secret belongs in repository source, tests, fixtures, documentation, or logs.

Retrieved legal text cannot override higher-priority instructions.

---

## 22. API and service lifecycle

The API must remain thin.

It owns:

- HTTP contracts;
- request validation;
- authentication/authorization boundaries;
- rate limiting;
- error mapping;
- readiness/liveness.

It must not implement retrieval, evidence, prompting, or document parsing directly.

Long-lived services should initialize expensive models and indexes once per process lifecycle and reuse them safely.

`/health` and `/ready` should remain semantically distinct:

- health = process is alive;
- ready = required runtime state is usable.

---

## 23. Portability

The core must target:

- Windows 10/11;
- WSL2;
- Linux;
- CPU-only systems;
- low-VRAM GPUs;
- modern workstation GPUs;
- remote inference APIs.

Platform-specific behavior must be isolated behind runtime abstractions.

One codebase should support multiple execution profiles.

---

## 24. Scalability strategy

Scale deliberately.

```text
correct single-node engine
        |
        v
resource-optimized single node
        |
        v
reliable API service
        |
        v
stateless horizontal replicas
        |
        v
externalized shared state/artifacts
        |
        v
distributed retrieval/queues only when measured demand requires them
```

Do not introduce:

- Kubernetes;
- microservices;
- distributed vector databases;
- complex queues;
- multi-region architecture

until workload evidence justifies the complexity.

The domain layer must remain reusable regardless of deployment topology.

---

## 25. Model strategy

LLMs are pluggable.

Potential backends may include:

- local Transformers models;
- Ollama;
- vLLM;
- OpenAI-compatible APIs;
- future providers.

The backend adapter must isolate provider-specific behavior.

### Training policy

Do not fine-tune merely because a dataset exists.

Before training, demonstrate that the observed bottleneck is likely model behavior rather than:

- poor retrieval;
- bad chunking/structure;
- missing metadata;
- incorrect temporal filtering;
- jurisdiction confusion;
- evidence-selection failure;
- prompt/schema problems.

Training changes must have:

- explicit objective;
- training dataset version;
- held-out evaluation;
- reproducibility metadata;
- resource budget;
- rollback path.

---

## 26. Product evolution

The roadmap is:

```text
Stage 1
Egyptian Legal Research + Evidence Reports
        |
Stage 2
Temporal / Amendment Intelligence
        |
Stage 3
Contradiction / Conflict Detection
        |
Stage 4
Fact-to-Rule Analysis
        |
Stage 5
Evidence-Constrained Agentic Workflows
        |
Stage 6
Egypt -> GCC/MENA Jurisdiction Packs
        |
Stage 7
API / SaaS
        |
Stage 8
Enterprise / Private Deployment / Governance
```

Agents are introduced only after the evidence, evaluation, authorization, and reliability boundaries are strong enough to constrain them.

---

## 27. Product and legal-safety boundary

The platform is a legal-information and legal-research system unless a future regulated product explicitly establishes a different legal/operational boundary.

The interface must distinguish:

```text
retrieved legal source
        |
model interpretation
        |
uncertainty / limitations
        |
missing evidence
```

The system must not present unsupported model output as authoritative law.

---

## 28. Code quality rules

Use:

- Python 3.12 as current baseline;
- type hints on public interfaces;
- `pathlib`;
- explicit exceptions;
- structured logging;
- deterministic behavior where practical;
- cohesive modules;
- tests for new behavior.

Avoid:

- magic numbers;
- global mutable state;
- broad exception swallowing;
- hard-coded machine paths;
- duplicate business logic;
- unnecessary dependencies;
- hidden side effects;
- unbounded process/thread creation;
- request-time model downloads;
- silent legal-data mutation.

---

## 29. Dependency and technology decision rules

A new dependency requires justification covering:

- responsibility;
- why existing components are insufficient;
- maintenance maturity;
- license;
- security posture;
- CPU/RAM/VRAM impact;
- startup impact;
- deployment impact;
- test strategy.

Prefer simple, mature components when they satisfy the requirement.

---

## 30. Development stage protocol

Every substantial stage follows the same process.

### A. Design

Define:

- problem;
- scope;
- interfaces;
- acceptance criteria;
- failure modes;
- resource budget;
- evaluation method.

### B. Inspect

Read existing code, contracts, tests, data, benchmarks and recent failure records.

### C. Implement

Make the smallest coherent change that satisfies the stage objective.

### D. Test

Run focused unit tests, integration tests and relevant static checks.

### E. Benchmark

Measure quality and resource behavior before/after.

### F. Adversarial review

Claude is a required implementation and adversarial-review partner for substantial stages.

Claude must challenge:

- architecture assumptions;
- legal-data semantics;
- edge cases;
- leakage;
- security;
- resource behavior;
- failure recovery;
- scalability;
- test adequacy;
- whether implementation actually realizes the intended behavior.

### G. Fix and re-test

Resolve material findings and repeat affected gates.

### H. Record

Update:

- documentation;
- decision records;
- benchmark artifacts;
- failure cases;
- release metadata.

### I. Release

Publish only when required gates pass.

---

## 31. Definition of done

A stage is not complete because the code runs once.

It is complete when its required acceptance criteria are demonstrated by reproducible evidence and the affected gates pass.

At minimum, the release decision must answer:

```text
What changed?
Why was it changed?
What does it improve?
What does it cost?
What could it break?
What tests passed?
What benchmarks changed?
What resource impact occurred?
What did Claude find?
What was fixed?
What remains known/unknown?
```

---

## 32. Non-negotiable prohibitions

```text
NO repository rewrite without evidence
NO duplicate pipeline implementations
NO silent legal-data mutation
NO fabricated legal metadata
NO fake metrics
NO benchmark leakage
NO unsupported legal claims
NO committed secrets
NO unbounded retries
NO unbounded worker/process spawning
NO request-time model/index rebuild
NO predictable model co-residency OOM
NO silent jurisdiction mixing
NO silent historical/current-law mixing
NO production self-modification from runtime failures
NO premature distributed architecture
NO fine-tuning without a measured justification
```

---

## 33. Current implementation baseline

Current implementation defaults are:

- Python 3.12;
- Windows/WSL/Linux portability;
- Quadro M2200 4 GB stress/development target;
- BGE-M3 dense retrieval baseline;
- FAISS CPU default;
- BM25 CPU supplemental retrieval;
- optional local Qwen generation;
- OpenAI-compatible remote generation.

These are defaults and test constraints, not global architectural limits.

---

## 34. Current known baseline and known limitations

Protected retrieval regression reference:

```text
MRR        0.835
Recall@1   0.75
Recall@3   0.90
Recall@5   0.95
Recall@10  1.00
```

Known limitation of current evaluation:

The existing self-retrieval smoke methodology derives query fragments from the same corpus used for retrieval. It is useful for catching gross retrieval regressions but is **not** evidence of real-user legal understanding, robust paraphrase handling, expert-level reasoning, or multi-evidence completeness.

The future evaluation system must explicitly close this gap.

---

## 35. Final success definition

The project succeeds when it can demonstrate, using reproducible evaluation and production-safe evidence, that it:

- retrieves the correct Egyptian legal authorities for realistic user questions;
- retrieves all material evidence required by multi-article questions;
- handles Arabic legal phrasing, paraphrase, terminology and user variation robustly;
- selects the correct jurisdiction;
- selects the correct legal version/time context;
- identifies and surfaces conflicts;
- produces answers whose material claims are traceable to evidence;
- abstains safely when evidence is insufficient;
- handles common runtime failures without unsafe behavior;
- learns from failures by converting them into controlled evaluation/regression cases;
- runs efficiently on constrained hardware;
- scales to stronger hardware/cloud without changing core domain contracts;
- supports independent LLM backends;
- maintains reproducible knowledge releases;
- provides auditable telemetry;
- can evolve into a commercial Legal Intelligence Platform without discarding the foundational engine.

---

## 36. Approval rule

This document is a **draft** until reviewed and explicitly approved.

Before promotion to `ARCHITECTURE_CONTRACT.md`, review for:

1. consistency with actual v3 implementation;
2. feasibility of each required invariant;
3. legal-domain semantics;
4. evaluation practicality;
5. resource feasibility;
6. security implications;
7. unnecessary complexity;
8. future scalability;
9. Claude implementation/review workflow.

After approval, `ARCHITECTURE_CONTRACT.md` becomes the canonical architecture contract and `CLAUDE.md` must instruct implementation agents to follow it.
