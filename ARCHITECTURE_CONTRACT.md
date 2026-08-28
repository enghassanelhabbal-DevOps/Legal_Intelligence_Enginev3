# ARCHITECTURE CONTRACT V4

> **Status:** Approved and authoritative for `feat/enterprise-foundation`.
>
> **Purpose:** Establish one coherent contract for the Legal Intelligence Engine / Platform that is truthful about the current v3 implementation, explicit about known gaps, and strong enough to guide future development without forcing premature infrastructure.

---

## 1. Product Mission

Build an **evidence-first, jurisdiction-aware, version-aware, resource-efficient Legal Intelligence Platform** for Arabic and emerging legal systems, starting with **Egypt**.

The product is **not** a generic legal chatbot. The durable product value is:

- high-quality legal retrieval;
- complete evidence selection for multi-authority questions;
- legal-context and query understanding;
- jurisdiction correctness;
- temporal/version correctness;
- evidence-supported legal reasoning;
- explicit uncertainty and safe abstention;
- auditable provenance and citations;
- measurable reliability and recovery;
- measurable CPU/RAM/VRAM/latency/throughput/cost efficiency;
- portability from constrained local hardware to cloud and enterprise environments.

The architecture must allow evolution from a single-node research engine into an API/SaaS/enterprise platform **without rewriting the legal-domain contracts**.

### First product wedge

The first practical product wedge is:

> **Egyptian legal research + evidence reports for professional users.**

Expected evolution:

```text
Egyptian Legal Research
        ↓
Temporal / Amendment Intelligence
        ↓
Fact-to-Rule / Case Analysis
        ↓
Contradiction / Conflict Intelligence
        ↓
Evidence-Constrained Legal Agents
        ↓
Egypt → GCC/MENA Jurisdiction Packs
        ↓
API / SaaS
        ↓
Enterprise / Private Deployment / Governance
```

Expansion must be explicit and evidence-driven. Adding another country's documents does not automatically make the corpus multi-jurisdiction capable.

---

## 2. Truthfulness of the Contract

This contract distinguishes three states:

### A. Verified current behavior

Behavior demonstrated by committed code, tests, benchmarks, or deployment evidence.

### B. Required architectural invariant

Behavior that future implementation must provide but may not yet exist fully.

### C. Known gap

A documented mismatch between the target architecture and current implementation. A gap is not evidence of failure by itself; it becomes a delivery item with an acceptance criterion.

No aspirational capability may be presented as a current product-quality claim.

---

## 3. Core Principles

### 3.1 Knowledge is independent from model weights

Legal knowledge is a first-class system asset.

Source text, authority, provenance, versions, amendments, releases, indexes, and evaluation assets are managed independently of the LLM.

Ordinary legal updates normally enter through:

```text
source → ingestion → validation → versioning → indexing → knowledge release
```

Retraining the base LLM is **not** the default method for updating legal facts.

### 3.2 Evidence before generation

The LLM is downstream of retrieval and evidence processing. It is a replaceable reasoning/generation component and is not the legal authority.

### 3.3 Measurement before claims

No claimed improvement in accuracy, latency, memory, throughput, cost, or reliability is valid without reproducible measurement.

### 3.4 Safe uncertainty

When evidence is missing, ambiguous, conflicting, outdated, or outside the requested jurisdiction/time scope, the system must surface that condition and may abstain.

### 3.5 No silent semantic mutation

Raw legal source material must be preserved. Normalization is a derived retrieval representation.

Jurisdiction, legal version, amendment, repeal, supersession, and provenance changes must be explicit.

### 3.6 No runtime self-modification

Runtime failures may produce telemetry, regression cases, or recommendations, but runtime operation must not silently change production code, prompts, thresholds, legal knowledge, or model weights.

All improvements occur through controlled engineering/data/model releases.

### 3.7 No fake success

A green test, passing endpoint, or successful model call is not evidence that the legal system is correct. Every substantive capability requires an appropriate benchmark.

---

## 4. Canonical System Architecture

The platform has three primary architectural planes plus cross-cutting controls.

```text
                         LEGAL INTELLIGENCE PLATFORM
                                  │
              ┌───────────────────┼───────────────────┐
              │                                       │
       KNOWLEDGE PLANE                        INTELLIGENCE PLANE
              │                                       │
 Source / Provenance                          User / QueryRequest
              ↓                                       ↓
 Parsing / Validation                        Query Understanding
              ↓                                       ↓
 Structure / Metadata                        Jurisdiction / Temporal Constraints
              ↓                                       ↓
 Version / Amendment                         Retrieval Planning
              ↓                                       ↓
 Knowledge Release                     Dense + Lexical Retrieval
              ↓                                       ↓
 Index Generation                        Candidate Union / Filtering
              ↓                                       ↓
 Evaluation Gate                              Reranking
              ↓                                       ↓
 Atomic Publish                             EvidenceSet
                                                      ↓
                                               Support / Conflict Checks
                                                      ↓
                                             Grounded Reasoning / Generation
                                                      ↓
                                               Verification / Abstention
                                                      ↓
                                         Answer + Citations + Warnings

        Cross-cutting: Evaluation / Observability / Resource / Failure / Security
```

### Canonical request flow

```text
User/API/UI
  → QueryRequest
  → Query Understanding
  → Jurisdiction + Temporal Constraints
  → Retrieval Plan
  → Dense + Lexical Retrieval
  → Candidate Union / Filtering
  → Reranking
  → EvidenceSet Construction
  → Evidence Support / Conflict Checks
  → Grounded Generation
  → Claim/Citation Validation
  → Abstention / Warning Decision
  → Answer
  → Telemetry
```

### Hard dependency direction

```text
API/UI → services → retrieval → reranking → evidence → generation
                         ↑
                         │
                   knowledge ← ingestion
                         │
                    evaluation
```

Cross-cutting resource/fault/observability infrastructure may observe all stages but must remain centralized rather than duplicated inside model backends.

### Layer rules

- `api/` contains HTTP, authentication, authorization, rate-limiting, validation boundaries, and error mapping.
- `ui/` contains presentation only.
- `services/` orchestrates; it does not own retrieval algorithms or prompt/business rules.
- `retrieval/` owns dense/lexical/hybrid candidate generation and retrieval filters.
- `reranking/` owns candidate scoring/ranking.
- `evidence/` owns evidence-set construction, support analysis, context shaping, and citation validation.
- `generation/` owns LLM interfaces and provider adapters.
- `knowledge/` owns legal identity, authority, provenance, temporal versions, and knowledge releases.
- `ingestion/` owns parsing, normalization, validation, hashing, deduplication, and metadata extraction.
- `evaluation/` owns datasets, metrics, benchmarks, leakage checks, and regression gates.
- `core/` owns stable contracts, configuration, runtime/resource policy, failure taxonomy, and logging.

No layer may create a second implementation of another layer's business logic for convenience.

---

## 5. Current Implementation Truth vs Target Architecture

The current v3 codebase already contains a strong modular foundation:

- startup/lifespan service construction in the FastAPI entrypoint;
- Qwen and OpenAI-compatible LLM backend abstraction;
- dense BGE-M3 retrieval;
- CPU-first FAISS index;
- BM25 retrieval;
- hybrid candidate handling;
- evidence/citation utilities;
- evaluation scripts;
- CI regression workflow;
- resource configuration and constrained-GPU considerations.

However, the current implementation also has known gaps that this contract must not hide.

### Known gaps

1. The CI regression harness currently exercises BM25/self-retrieval, not the full production dense + BM25 + reranker pipeline.
2. The historical 0.835 retrieval baseline cannot currently be reproduced from an authoritative committed harness and must not be treated as a verified CI baseline.
3. The root Streamlit entrypoint contains duplicated retrieval logic and therefore violates the intended single-pipeline architecture.
4. The root `app.py` also contains a vendored Gemini generation implementation that duplicates the canonical generation adapter boundary; this is a known Stage 3 migration item tracked by DR-013/DR-014.
5. Several domain contracts described below are target contracts and are not yet fully implemented.
6. GPU resource measurements for the current full hybrid/reranker pipeline on the Quadro M2200 remain outstanding.

These gaps are tracked implementation work, not reasons to rewrite the repository.

---

## 6. Retrieval Baselines and Baseline Governance

### 6.1 Historical reference

The values below were previously documented as a protected hybrid retrieval baseline:

```text
MRR        = 0.835
Recall@1   = 0.75
Recall@3   = 0.90
Recall@5   = 0.95
Recall@10  = 1.00
```

**Status: UNVERIFIED HISTORICAL REFERENCE.**

The repository does not currently contain a reproducible authoritative harness proving these exact values for the current production pipeline. Therefore they are **not** release gates and must not be reported as measured current performance.

### 6.2 Current CI smoke reference

The repository currently has a BM25-based self-retrieval evaluation over the real corpus and a CI gate around that evaluation.

This is useful for regression detection but is intentionally easier than realistic user-style legal retrieval.

It must be labeled:

> **SELF-RETRIEVAL SMOKE BASELINE — REGRESSION GUARD ONLY**

The actual enforced thresholds and latest measured values must be read from the versioned benchmark artifact and CI configuration, not copied manually into this contract.

### 6.3 Full pipeline baseline requirement

Stage 4 must establish a reproducible benchmark for:

```text
Dense BGE-M3
+ BM25
+ candidate union
+ reranker
+ evidence selection
```

The benchmark must report quality and resource behavior using the same pipeline used by the serving path.

### 6.4 Mandatory retrieval metrics

At minimum:

- MRR;
- Recall@1/3/5/10;
- candidate recall before reranking;
- Full Recall@K / evidence-set coverage for multi-evidence cases;
- missing-evidence rate;
- latency;
- CPU/RAM/VRAM impact;
- throughput where workload testing is relevant.

---

## 7. Canonical Legal Domain Model

The legal identity model must eventually support:

```text
LegalDocument
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

Missing metadata must remain explicit (`null`, `unknown`, or controlled missing state) and must never be fabricated.

### First-class domain contracts and earliest required stage

| Contract | Earliest required stage | Status |
|---|---|---|
| `LegalDocument` | Foundation | Current/partial |
| `LegalVersion` | Knowledge Versioning | Target |
| `LegalCitation` | Evidence Foundation | Target |
| `LegalSource` | Knowledge Foundation | Target |
| `RetrievalHit` | Retrieval | Current/partial |
| `EvidenceItem` | Evidence Foundation | Target |
| `EvidenceSet` | Evidence Foundation | Target |
| `QueryRequest` | API Foundation | Current/partial |
| `QueryUnderstanding` | Query Intelligence | Target |
| `RetrievalPlan` | Query Intelligence | Target |
| `QueryResponse` | API Foundation | Current/partial |
| `Answer` | Generation | Current |
| `EvaluationCase` | Evaluation Foundation | Target/partial |
| `EvaluationResult` | Evaluation Foundation | Target |
| `KnowledgeRelease` | Knowledge Release | Target |
| `ModelInfo` | Runtime/Observability | Target/partial |
| `TimingInfo` | Runtime/Observability | Target/partial |
| `ResourceInfo` | Resource Intelligence | Target |
| `FailureEvent` | Reliability Foundation | Target |

The table is a sequencing device. It is **not** a requirement to implement all contracts in Stage 1.

---

## 8. Knowledge, Provenance, Authority, and Versioning

Every source update follows:

```text
raw source
  ↓
provenance / license / authority validation
  ↓
parse
  ↓
schema validation
  ↓
raw-text preservation
  ↓
search normalization
  ↓
legal structure extraction
  ↓
metadata enrichment
  ↓
deduplication / near-duplicate analysis
  ↓
version / amendment / repeal / supersession analysis
  ↓
knowledge release candidate
  ↓
index generation
  ↓
evaluation gate
  ↓
atomic publish
```

Knowledge releases must be:

- deterministic;
- versioned;
- identifiable;
- auditable;
- reproducible;
- rollbackable.

### Authority classes

At minimum distinguish:

- primary official/legal sources;
- judicial decisions;
- regulatory/administrative sources;
- secondary legal sources;
- user-provided/private material.

Authority level must be represented explicitly and never fabricated from text similarity alone.

---

## 9. Temporal Semantics

The system must support legal time, including when available:

```text
publication_date
effective_from
effective_to
amendment_date
repeal_date
supersedes
superseded_by
version_id
```

A query may use an explicit date or a selected legal-as-of date.

The engine must not silently combine incompatible historical and current versions.

Temporal correctness is an evaluation dimension, not merely metadata presence.

---

## 10. Jurisdiction Semantics

Every knowledge item has an explicit jurisdiction.

Default behavior:

```text
EG ≠ SA ≠ AE ≠ QA ≠ other jurisdictions
```

Cross-jurisdiction retrieval is disabled by default unless the user explicitly requests comparison or the product is operating in a declared comparison mode.

Similar wording is not equivalence.

---

## 11. Query Understanding

Before retrieval, the system should progressively derive a structured representation such as:

```text
language
jurisdiction
country/legal system
legal domain
reference / effective date
query intent
question type
candidate authority types
single-hop / multi-hop
required evidence types
risk / ambiguity flags
```

Supported query classes should eventually include:

- direct article lookup;
- rule explanation;
- conditions/requirements;
- exceptions;
- fact-to-rule application;
- multi-article synthesis;
- historical/temporal question;
- jurisdiction comparison;
- contradiction/conflict analysis;
- evidence-sufficiency query.

Query understanding may recommend a retrieval plan but must not invent legal facts or override explicit user constraints.

---

## 12. Retrieval and Ranking

Default retrieval:

```text
Query
 ↓
Query normalization / understanding
 ↓
Dense + Lexical Retrieval
 ↓
Candidate Union
 ↓
Jurisdiction / Temporal / Metadata Filtering
 ↓
Reranking
 ↓
Evidence Selection
```

Dense retrieval and lexical retrieval must be independently measurable.

Reranking must be batch-oriented and resource bounded.

Any change to fusion/ranking requires:

- named dataset version;
- named benchmark version;
- baseline configuration;
- experimental configuration;
- before/after quality metrics;
- latency delta;
- resource delta;
- failure observations.

No algorithm is preferred because it is fashionable; it must earn adoption through measured evidence or solve a documented limitation.

---

## 13. Arabic Legal-Language Intelligence

Arabic normalization is retrieval-oriented. The raw authoritative text must remain untouched.

The system must support and evaluate:

- alef variants;
- ya / alif-maqsura variation;
- diacritics;
- tatweel;
- punctuation variation;
- whitespace/noise;
- spelling variation;
- article-number expressions;
- legal abbreviations;
- legal synonyms/terminology;
- formal Arabic paraphrases;
- realistic colloquial user phrasing where relevant;
- Arabic/English mixed queries.

Evaluation must distinguish:

```text
Arabic retrieval robustness
        ≠
legal understanding
```

The normalization layer must be configurable and safe to evolve without changing authoritative text.

---

## 14. Legal Understanding

Legal understanding must be evaluated independently from retrieval.

Target capabilities:

1. Issue identification.
2. Applicable rule identification.
3. Condition detection.
4. Exception detection.
5. Relevant-fact extraction.
6. Fact-to-rule application.
7. Multi-article synthesis.
8. Temporal rule selection.
9. Jurisdiction selection.
10. Conflict identification.
11. Evidence sufficiency assessment.
12. Safe abstention.

A correct retrieval result does not prove correct legal reasoning.

---

## 15. Evidence Architecture

Evidence is a first-class system object.

An `EvidenceItem` should retain where available:

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

An `EvidenceSet` is the complete selected evidence context for one answer.

### Claim-to-evidence mapping

```text
Claim C1 → Evidence E1, E3
Claim C2 → Evidence E4
Claim C3 → unsupported → failure / abstention
```

Material claims must have traceable evidence identifiers.

Citation/support validation must be **enforced**, not only logged as a warning.

Support semantics should eventually distinguish:

- directly supports;
- partially supports;
- contradicts;
- context-only;
- insufficient;
- outdated;
- conflicting authority.

---

## 16. Grounded Generation

Generation receives only bounded, structured, validated evidence context.

Prompt boundaries must distinguish:

```text
SYSTEM INSTRUCTIONS
USER REQUEST
LEGAL EVIDENCE
OUTPUT SCHEMA
```

Retrieved text is untrusted content and cannot override higher-priority instructions.

Generation must:

- support structured output;
- return evidence identifiers;
- expose uncertainty/warnings;
- refuse unsupported claims;
- support abstention;
- distinguish retrieved law from model interpretation;
- avoid exposing hidden chain-of-thought.

A product-facing reasoning summary may be returned, but internal hidden reasoning must not be exposed.

---

## 17. Abstention and Answer Safety

The decision path should be:

```text
Retrieve
  ↓
Evidence sufficiency
  ├─ sufficient → reason / generate
  ├─ ambiguous → warn / narrow / request constraint
  ├─ contradictory → surface conflict
  ├─ outdated → resolve correct temporal version
  └─ insufficient → abstain
```

Abstention quality must be measured.

False confidence is a higher-severity failure than a controlled abstention in high-risk legal contexts.

---

## 18. Evaluation Architecture

Evaluation is a first-class subsystem and release gate.

### Retrieval

MRR, Recall@K, candidate recall, latency.

### Multi-evidence retrieval

Full Recall@K, evidence-set coverage, missing-evidence rate.

### Reranking

Ranking quality, contribution, latency/resource cost.

### Arabic robustness

Paraphrase, spelling, normalization, terminology, mixed-language, article reference.

### Legal understanding

Issue, rule, exceptions, application, multi-article synthesis.

### Entailment / support

Support rate, unsupported-claim rate, contradiction rate.

### Grounded generation

Citation validity, citation coverage, groundedness, abstention handling.

### Temporal correctness

Historical rule selection, amendment, repeal, supersession.

### Jurisdiction correctness

Selection accuracy, cross-jurisdiction confusion.

### Reliability

Failure rate, recovery success, degraded-mode success, restart safety, reproducibility.

### Efficiency

CPU, RAM, VRAM, latency, throughput, token use, estimated cost.

---

## 19. Evaluation Dataset Governance

Every dataset must be profiled before use for:

- provenance;
- license/usage rights;
- schema and field meaning;
- source authority;
- language;
- jurisdiction;
- legal-time coverage;
- duplicates/near-duplicates;
- annotation quality;
- task suitability;
- contamination/leakage risk.

Every dataset must receive one or more explicit roles:

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

Prefer source-level, law-level, or other semantic-grouped splits over random record splits when overlap could leak legal text.

The held-out benchmark must not be used for training, tuning, prompt selection, threshold selection, or model selection.

A larger dataset is not automatically a better dataset.

---

## 20. Required Dataset Evaluation Levels

Every substantial legal dataset should be tested across:

```text
L1  Direct article lookup
L2  Paraphrase
L3  Natural user phrasing
L4  Fact pattern
L5  Multi-article evidence
L6  Rule + exception
L7  Temporal / historical
L8  Jurisdiction confusion
L9  Contradiction / conflict
L10 Insufficient evidence / abstention
```

This is the minimum design language for the future Egyptian legal benchmark.

---

## 21. Resource Architecture

Resource efficiency is a product requirement.

The runtime begins with:

```text
Hardware discovery
      ↓
Resource budget
      ↓
Execution profile
      ↓
Bounded concurrency / batching
      ↓
Model placement
      ↓
Adaptive execution
      ↓
Telemetry
```

Profiles:

- `cpu-minimal`;
- `balanced`;
- `accelerated`;
- `remote-llm`.

### Requirements

- GPU is optional.
- FAISS/BM25 remain CPU-first where appropriate.
- No assumption of Tensor Cores, FP8, or one GPU architecture.
- No predictable model co-residency OOM.
- Bounded workers and queues.
- Bounded retries.
- Memory-aware batching.
- Explicit model load/unload/offload policy.
- Graceful degradation where possible.
- No request-time model downloads.

### Reference development hardware

The Quadro M2200 4 GB is a **stress and compatibility target**, not a universal maximum.

Current full-pipeline GPU resource measurements on that device remain a required benchmark gap until actually reproduced.

---

## 22. Fault Intelligence

The runtime failure lifecycle is:

```text
Failure
  ↓
Classify
  ↓
Contain
  ↓
Recover / Degrade
  ↓
Record failure fingerprint
  ↓
Create regression/evaluation case
  ↓
Controlled fix
  ↓
Benchmark
  ↓
Release
```

### Failure fingerprint

Capture where applicable:

```text
failure_id
operation
stage
error_class
error_signature
software_version
model_version
knowledge_release
dataset/evaluation_version
hardware_profile
resource_profile
recovery_action
recovery_outcome
timestamp
```

Runtime learning must not silently modify production code or weights.

### Recovery properties

Recovery must be:

- bounded;
- deterministic where feasible;
- observable;
- reversible;
- safe under repeated failure.

Typical categories:

- invalid input;
- corrupted artifact;
- model load failure;
- OOM;
- timeout;
- backend/API failure;
- dependency incompatibility;
- retrieval miss;
- evidence insufficiency;
- citation mismatch;
- version/jurisdiction conflict.

---

## 23. Observability and Cost Intelligence

Important requests and benchmark runs should carry identifiers and record, where applicable:

- knowledge release;
- retriever version;
- reranker version;
- model/backend;
- execution profile;
- stage latency;
- CPU/RAM/VRAM signals;
- warnings/errors;
- recovery action;
- dataset/evaluation version;
- token usage;
- estimated inference cost.

Instrumentation must remain lightweight on constrained hardware.

Standard metrics/tracing integrations may be introduced when justified by workload requirements.

---

## 24. API and Serving Lifecycle

The serving system must:

- initialize heavyweight services once per process;
- avoid model/index reload on every request;
- provide separate liveness and readiness semantics;
- expose stable versioned API contracts;
- validate inputs before expensive processing;
- keep ML implementation out of the HTTP layer;
- make failure and degradation states explicit.

### Single-process deployment constraint

Some deployment platforms may provide only one application process (for example, a Streamlit-only hosting pattern).

That constraint **does not justify vendoring retrieval/generation logic into the UI**.

Required design:

```text
Single-process UI deployment
        ↓
UI imports QueryService
        ↓
Canonical src/legal_ai pipeline
```

and:

```text
Multi-process / production deployment
        ↓
UI / clients
        ↓
FastAPI service
        ↓
Canonical src/legal_ai pipeline
```

The duplicated root `app.py` retrieval implementation and vendored Gemini generation implementation are **known Stage 3 cleanup tasks**. They must be removed once the canonical paths are proven against the supported deployment modes.

---

## 25. Security

Treat all external and user-provided content as untrusted:

- user queries;
- uploaded legal documents;
- retrieved text;
- model output;
- external APIs/connectors.

Required controls include:

- strict schema validation;
- file-size and MIME limits;
- safe path handling;
- provenance validation;
- prompt-injection defense;
- authentication and authorization boundaries;
- rate limiting;
- secrets outside source control;
- structured audit events;
- tenant/data isolation for enterprise deployments.

Example/template secret files are allowed only with placeholders and must never contain live credentials.

---

## 26. Portability

The core must target:

- Windows 10/11;
- WSL2;
- Linux;
- CPU-only hosts;
- constrained GPUs;
- modern GPUs;
- remote inference APIs.

Platform-specific logic must be isolated behind runtime abstractions.

---

## 27. Scalability Strategy

Scale in this order:

```text
Correct single node
      ↓
Measured resource optimization
      ↓
Reliable API
      ↓
Stateless horizontal API replicas
      ↓
Externalized shared state/artifacts
      ↓
Distributed queues/search/services only when measured demand requires them
```

No premature Kubernetes, microservices, distributed vector stores, or complex orchestration merely for architectural aesthetics.

---

## 28. Model Strategy

The system is model-agnostic at the architecture boundary.

Potential backends include:

- local Transformers;
- Qwen or equivalent local model;
- Ollama;
- vLLM;
- OpenAI-compatible remote endpoints;
- Gemini through the canonical `GeminiBackend` adapter;
- future providers.

The model is a replaceable component.

Model selection must consider:

- legal quality;
- Arabic capability;
- latency;
- memory;
- cost;
- reliability;
- licensing/usage constraints.

### Fine-tuning rule

Fine-tuning is not a default response to poor retrieval or stale legal knowledge.

Before fine-tuning, establish whether the observed problem is caused by:

```text
retrieval
reranking
query understanding
evidence selection
legal data quality
prompt/structured output
generation quality
```

Only then decide whether model training is justified.

---

## 29. Product Evolution Boundaries

The technical roadmap supports:

1. Egyptian legal research + evidence reports.
2. Temporal/amendment intelligence.
3. Contradiction/conflict detection.
4. Fact-to-rule analysis.
5. Evidence-constrained agentic workflows.
6. Jurisdiction packs: Egypt → GCC/MENA.
7. API/SaaS.
8. Enterprise/private deployment/governance/data residency.

The first commercial experience should solve one painful professional workflow extremely well before broad feature expansion.

---

## 30. Claude Implementation and Adversarial Review Protocol

Claude is a **mandatory implementation and adversarial review partner for substantial engineering stages**.

However, review and implementation are distinct roles.

### Required stage loop

```text
Design + acceptance criteria
        ↓
Inspect current implementation
        ↓
Implement one coherent change
        ↓
Focused tests
        ↓
Integration tests
        ↓
Lint / type checks
        ↓
Relevant benchmark
        ↓
Resource measurement
        ↓
Claude adversarial review
        ↓
Human/project-owner decision on findings
        ↓
Authorized implementation step
        ↓
Re-test / re-benchmark
        ↓
Release decision
```

### Critical boundary

Claude's review output is advisory evidence for the engineering process. **The reviewing agent must not unilaterally convert its own findings into production changes without an explicitly authorized implementation step.**

This preserves the distinction between:

```text
Review
≠
Autonomous production self-modification
```

---

## 31. Change Governance

A meaningful change must declare:

- problem;
- expected behavior;
- scope;
- acceptance criteria;
- affected contracts;
- expected resource impact;
- failure modes;
- test plan;
- benchmark plan.

A repository rewrite requires explicit evidence that incremental evolution is no longer safe or maintainable.

New dependencies require:

- responsibility;
- maintenance rationale;
- resource impact assessment;
- security/license assessment;
- tests.

---

## 32. No-Duplicate Implementation Rule

The repository must have one canonical implementation for each business capability.

Particularly:

```text
Retrieval → one canonical retrieval path
Generation → one canonical adapter layer
Normalization → one canonical normalization implementation
Evidence → one canonical evidence contract
Evaluation → one canonical metric/benchmark implementation per metric
```

Compatibility entrypoints may exist, but they must delegate to canonical modules rather than vendor copies of logic.

The existing root `app.py` duplication is therefore a **known technical-debt item**, not an architectural exception.

### Presumptive-duplication rule

Any new capability implemented first in `app.py`, or another presentation/deployment convenience entrypoint, is **presumptively a duplicate-implementation violation** unless it is presentation-only or has a named migration path into the canonical `src/legal_ai` layer before the relevant stage is considered complete.

The current root `app.py` retrieval and Gemini generation implementations are explicit examples of this rule and are tracked for Stage 3 consolidation.

---

## 33. Current Baseline and Known-Limitation Register

This register remains visible after approval and must evolve as gaps close.

| Item | Truth | Required action |
|---|---|---|
| Historical 0.835 retrieval numbers | Unverified historical reference | Reproduce or retire |
| CI smoke baseline | Enforced BM25/self-retrieval regression guard | Keep clearly labeled |
| Full hybrid CI coverage | Missing | Add controlled full-pipeline benchmark |
| Root `app.py` duplicate retrieval | Known violation | Remove after canonical UI validation |
| Root `app.py` duplicate generation (Gemini) | Known violation | Implement canonical `GeminiBackend`, prove parity, then remove vendored path |
| Domain contracts | Partial | Add by stage, not all at once |
| M2200 full-pipeline GPU benchmark | Outstanding | Measure before claiming accelerated profile |
| Human expert benchmark | Missing | Build Egyptian legal benchmark |
| Temporal benchmark | Missing | Build version/amendment cases |
| Jurisdiction benchmark | Missing | Build Egypt/GCC confusion cases when multi-jurisdiction begins |
| Failure regression corpus | Early/partial | Formalize after failure taxonomy implementation |

---

## 34. Roadmap Staging

### Stage 0 — Contract and repository truth

- approve V4 contract;
- reconcile implementation vs contract;
- eliminate misleading baseline claims;
- record known gaps.

### Stage 1 — Dataset Intake + Evaluation Foundation

- dataset profiler;
- provenance/license metadata;
- schema profiling;
- deduplication/leakage checks;
- task classification;
- grouped train/validation/test/challenge split;
- evaluation case contract;
- human/expert benchmark schema.

### Stage 2 — Resource + Fault Foundation

- hardware discovery;
- resource profiles;
- adaptive bounded batching;
- memory-pressure handling;
- failure taxonomy;
- recovery policies;
- failure fingerprints.

### Stage 3 — Canonical Pipeline Consolidation + Fault Intelligence

- remove root duplicate retrieval logic;
- enforce canonical QueryService path;
- strengthen API/UI separation;
- implement and validate canonical `GeminiBackend` with parity tests and bounded provider fallback behavior;
- remove vendored Gemini generation from root `app.py` after parity is demonstrated;
- stabilize domain contracts;
- formalize fault classification/recovery and regression-case capture.

### Stage 4 — Full Retrieval Benchmark

- full dense + BM25 + reranker benchmark;
- reproducible baseline;
- candidate recall;
- multi-evidence evaluation;
- M2200 resource benchmark.

### Stage 5 — Arabic Legal Understanding

- realistic user queries;
- paraphrase suites;
- Arabic robustness;
- fact-pattern evaluation;
- human/expert labels.

### Stage 6 — Evidence and Groundedness

- first-class EvidenceItem/EvidenceSet;
- claim-to-evidence mapping;
- support/contradiction semantics;
- enforced citation gate;
- abstention benchmark.

### Stage 7 — Knowledge Versioning

- authority model;
- legal version graph;
- amendments;
- repeal/supersession;
- atomic knowledge releases.

### Stage 8 — Legal Research Product

- research workflow;
- evidence report;
- professional UX;
- auditability.

### Stage 9 — Advanced Intelligence

- contradiction analysis;
- fact-to-rule analysis;
- evidence-constrained agents;
- cost-aware model routing.

### Stage 10 — Jurisdiction Expansion

- Egypt stabilization;
- GCC/MENA jurisdiction packs;
- cross-jurisdiction comparison mode.

### Stage 11 — Commercial Platform

- API/SaaS;
- enterprise identity;
- tenant isolation;
- private deployments;
- governance/data residency;
- horizontal scaling as workload evidence justifies it.

---

## 35. Definition of Done

A feature or stage is complete only when the affected gates pass:

```text
Problem / acceptance criteria
        ↓
Code / implementation
        ↓
Focused tests
        ↓
Integration tests
        ↓
Lint / type checks
        ↓
Relevant benchmark
        ↓
Resource measurement
        ↓
Claude adversarial review
        ↓
Authorized finding resolution
        ↓
Re-test / re-benchmark
        ↓
Documentation / decision record
        ↓
Release decision
```

A metric regression may be accepted only with a documented reason and explicit project-owner approval.

---

## 36. Final Definition of Success

The project succeeds when reproducible evidence demonstrates that it can:

- retrieve the correct Egyptian legal authorities for realistic user questions;
- retrieve the complete material evidence for multi-article questions;
- handle Arabic legal paraphrase and user language robustly;
- distinguish retrieval quality from legal understanding;
- respect jurisdiction and legal time/version;
- ground material legal claims in traceable evidence;
- identify contradictions and insufficient evidence;
- abstain safely when necessary;
- survive resource pressure and common runtime failures gracefully;
- convert meaningful failures into regression/evaluation cases;
- operate efficiently on constrained hardware;
- move to stronger hardware/cloud without changing core domain contracts;
- evolve into a commercial Legal Intelligence Platform without discarding the foundational engine.

---

## 37. Approval Record

**Promotion status:** APPROVED

**Source:** `ARCHITECTURE_CONTRACT_V4_RECONCILED_DRAFT.md`

**Promotion action:** Promoted to the authoritative `ARCHITECTURE_CONTRACT.md` on `feat/enterprise-foundation` after Claude adversarial review and full-system verification.

The authoritative contract may evolve through controlled, reviewable changes. Any material architectural change must update this contract, the relevant foundation documents, and the engineering decision register before the change is considered complete.

---

**End of Authoritative Architecture Contract V4.**
