# Enterprise Evolution Roadmap

## Product north star

Build an evidence-first, jurisdiction-aware, version-aware Legal Intelligence Platform for Arabic and emerging legal systems.

The engine is not an autonomous lawyer. It is a controlled intelligence system that retrieves authoritative legal material, selects evidence, reasons over grounded context, exposes uncertainty, and preserves an audit trail.

## Core design principles

1. Knowledge is independent from model weights.
2. Every material legal claim must be traceable to evidence.
3. Retrieval recall is protected before ranking optimization.
4. Wrong-jurisdiction retrieval is a correctness failure, not a minor ranking issue.
5. Historical legal questions must resolve against the correct legal version.
6. Resource usage is budgeted and adaptive.
7. Runtime failures trigger recovery and structured learning, not uncontrolled self-modification.
8. Every ML improvement must be benchmarked.
9. Legal-data updates must not require LLM retraining.
10. The same core must run on constrained hardware and scale to cloud infrastructure.

## Target architecture

```text
Client / UI / SDK
        |
        v
API Gateway + Auth + Rate Limit
        |
        v
Query Orchestrator
        |
        +--> Query Understanding
        |       - language
        |       - jurisdiction
        |       - effective date
        |       - legal task
        |       - ambiguity
        |
        +--> Retrieval Plane
        |       - lexical retrieval
        |       - dense retrieval
        |       - metadata filters
        |       - temporal filters
        |       - candidate fusion
        |       - reranking
        |
        +--> Evidence Plane
        |       - evidence selection
        |       - provenance
        |       - conflict detection
        |       - citation validation
        |
        +--> Reasoning Plane
        |       - LLM adapter
        |       - constrained reasoning
        |       - structured answer
        |       - confidence/uncertainty
        |
        +--> Reliability Plane
        |       - resource manager
        |       - fault manager
        |       - recovery manager
        |       - circuit breakers
        |       - telemetry
        |
        +--> Evaluation Plane
                - offline benchmarks
                - regression gates
                - shadow evaluation
                - error analysis
                - release gates

Knowledge Plane
  ingest -> validate -> normalize -> structure -> version -> deduplicate
          -> provenance -> index -> evaluate -> publish knowledge release
```

## Phase 0 — Repository hardening

Goals:
- establish one canonical implementation
- remove/disable legacy entry points
- eliminate committed secrets
- make CI trustworthy
- confirm startup/shutdown lifecycle
- define resource profiles

Exit criteria:
- one documented API entry point
- one documented UI entry point
- clean dependency graph
- clean secret handling
- fast test tier green
- existing retrieval baseline reproduced

## Phase 1 — Resource intelligence

Add a resource manager that detects available CPU, RAM, GPU, VRAM, disk, and process constraints without requiring optional accelerator libraries.

Profiles:
- `minimal`: CPU-first, small batches, low memory
- `balanced`: normal local workstation behavior
- `accelerated`: larger batches where measured safe

Adaptive behavior:
- batch-size backoff after resource failures
- concurrency limits
- inference queueing
- model offload/unload
- CPU fallback where quality remains acceptable
- bounded retries
- circuit breakers for failing remote providers

The resource manager must never silently change legal semantics. It may change execution strategy, not legal filtering or evidence rules.

## Phase 2 — Fault intelligence

Every operational failure emits a structured event:

```json
{
  "failure_id": "...",
  "class": "oom",
  "component": "reranker",
  "operation": "score",
  "hardware_profile": "...",
  "resource_snapshot": {},
  "recovery": "batch_backoff",
  "outcome": "recovered",
  "latency_ms": 0
}
```

A recurring failure can be promoted into a deterministic regression test or benchmark fixture.

Do not perform automatic code changes, model retraining, or production policy changes from failure events.

## Phase 3 — Knowledge quality and legal structure

Upgrade the current article model into a version-aware knowledge model supporting:
- jurisdiction
- legal system
- law identity
- article/section hierarchy
- source authority
- publication date
- effective date
- repeal date
- amendment relation
- supersession relation
- provenance
- content/document hashes
- knowledge-release version

Introduce immutable knowledge releases so a query can be reproduced against the exact legal state used at that time.

## Phase 4 — Retrieval science

Current dense + BM25 architecture is retained as baseline.

Improve in controlled experiments:
- Arabic-specific lexical normalization
- morphology-aware expansion where justified
- query rewriting only when benchmark evidence supports it
- metadata-aware retrieval
- legal citation/number boosting
- temporal filtering
- multi-hop candidate generation
- graded relevance and nDCG

Never optimize only MRR. Multi-article legal questions require full-recall metrics.

## Phase 5 — Legal understanding and entailment

Separate the reasoning problem from retrieval.

For a fixed gold evidence set, test:
- rule identification
- exception recognition
- issue spotting
- applicability
- procedural sequence
- legal entailment
- contradiction
- temporal applicability
- abstention

This tells us whether a bad answer came from:
- retrieval failure
- evidence selection failure
- reasoning failure
- generation failure

## Phase 6 — Evidence-first answer engine

Every answer should expose a machine-readable structure:

```text
question
jurisdiction
effective_date
answer
legal_issues
claims[]
  claim
  evidence_ids[]
  support_status
citations[]
contradictions[]
uncertainty[]
warnings[]
timing
knowledge_release
model_info
```

A citation with no supporting evidence is invalid.

## Phase 7 — Egyptian Legal Intelligence MVP

Build a curated Egypt benchmark and product workflow first.

Priority workflows:
1. legal research report
2. article/authority discovery
3. multi-article issue analysis
4. amendment-aware research
5. evidence package generation

The benchmark should contain real user-like questions authored independently from the source text, not only article fragments.

## Phase 8 — Arabic / MENA expansion

Represent each jurisdiction as a separate knowledge package.

Do not merge jurisdictions into one undifferentiated corpus.

Start with Egypt, then evaluate Saudi/UAE/GCC expansion based on data access, customer demand, and legal-source licensing.

## Phase 9 — Agentic workflows

Agents are introduced only after evidence, temporal filtering, and evaluation are reliable.

Agents may plan and call tools, but all legal assertions remain evidence-constrained.

Initial agents:
- Research Agent
- Authority Verification Agent
- Amendment Impact Agent
- Case Analysis Agent
- Evidence Report Agent

## Phase 10 — Enterprise platform

Add:
- tenants
- matters/workspaces
- RBAC
- SSO
- audit trails
- encryption
- data retention controls
- private deployment
- API/SDK
- observability
- cost/resource budgets

## Data strategy

External datasets may be used for research, benchmarking, or optional training only after licensing/provenance review.

Candidate Arabic legal benchmark references include:
- ArabLegalEval: Arabic legal knowledge benchmark based on Saudi legal documents.
- ALARB: Arabic legal argument reasoning benchmark using 13K+ Saudi commercial court cases.
- MizanQA: Moroccan legal QA benchmark.
- COLIEE: legal retrieval and entailment benchmark methodology.

These are references for methodology, not substitutes for an Egypt-specific gold dataset.

## Training policy

Do not fine-tune the generator simply because more legal text is available.

First determine whether the new dataset should be used for:
- knowledge/indexing
- retrieval training
- reranker training
- embedding evaluation
- reasoning evaluation
- instruction tuning

Ordinary legislation updates belong in the knowledge layer.

Fine-tuning is justified only when an evaluation shows that a model-side capability is the bottleneck and the data/license/compute make training worthwhile.

## Decision gates requiring explicit product/legal review

These are the points where domain-owner input is required:

1. authoritative Egyptian source hierarchy
2. acceptable legal-source licenses
3. definition of a "correct" legal answer
4. acceptable confidence/abstention behavior
5. intended professional user (lawyer, legal researcher, company counsel, student)
6. first paid workflow
7. jurisdictions for commercial launch
8. data retention and privacy requirements

Engineering may continue safely before these decisions, but these decisions should block high-stakes product claims and production legal recommendations.
