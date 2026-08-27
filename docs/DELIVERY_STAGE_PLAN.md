# Delivery Stage Plan

## Operating principle

Build the smallest coherent system that proves each important assumption before introducing the next layer of complexity.

Every stage follows:

```text
Design
→ Inspect
→ Implement
→ Test
→ Benchmark
→ Resource measure
→ Claude adversarial review
→ Fix
→ Re-test
→ Record
→ Release
```

## Stage 0 — Contract reconciliation

Status: review.

Outputs:
- approved architecture contract;
- approved Claude instructions;
- document index;
- decision register;
- verified-vs-target inventory.

Exit criteria:
- no contradiction between authoritative docs;
- baseline status explicitly classified;
- current known gaps documented.

## Stage 1 — Data intake + evaluation foundation

Goal: make datasets measurable, versioned, leakage-safe inputs.

Implement:
- dataset manifest schema;
- intake/profiling CLI;
- provenance/license fields;
- schema validation;
- duplicate/near-duplicate checks;
- leakage checks;
- task-role classification;
- versioned split manifest;
- benchmark manifest.

Exit criteria:
- current 952-article corpus can be profiled;
- second dataset can be profiled without custom code;
- held-out benchmark is isolated;
- reports are reproducible.

## Stage 2 — Canonical runtime/resource foundation

Goal: portable bounded execution.

Implement:
- hardware discovery;
- resource profiles;
- bounded workers/queues;
- timeout/retry policies;
- model residency policy;
- resource telemetry;
- adaptive batch policy.

Exit criteria:
- CPU-minimal and remote-LLM paths work;
- constrained GPU path has measured limits;
- no unbounded retry/spawn behavior.

## Stage 3 — Fault intelligence

Goal: survive common failures and capture them safely.

Implement:
- error taxonomy;
- normalized FailureEvent;
- recovery policies;
- graceful degradation;
- failure fingerprint;
- regression-case export.

Exit criteria:
- injected failures produce deterministic bounded recovery;
- failures remain observable;
- no production self-modification.

## Stage 4 — Retrieval benchmark upgrade

Goal: replace smoke-only confidence with real user-style measurement.

Implement:
- expert-labeled query set;
- multi-evidence gold sets;
- paraphrase sets;
- Arabic robustness sets;
- candidate recall reporting;
- full hybrid benchmark.

Exit criteria:
- full production retrieval path benchmarked;
- metrics reproducible;
- category-level error analysis available.

## Stage 5 — Retrieval/reranker optimization

Only after Stage 4.

Experiments may cover:
- query expansion;
- normalization variants;
- candidate count;
- fusion methods;
- reranker models;
- batch size;
- score calibration.

Acceptance requires quality/resource evidence.

## Stage 6 — Evidence enforcement

Goal: make evidence a hard correctness boundary.

Implement:
- EvidenceItem;
- EvidenceSet;
- claim-to-evidence mapping;
- support classification;
- citation validation;
- insufficient-evidence gate;
- conflict flags.

Exit criteria:
- generation cannot bypass evidence validation;
- unsupported material claims are failures.

## Stage 7 — Legal understanding benchmark + query understanding

Implement:
- QueryRequest/Understanding/Plan contracts;
- issue/rule/exception extraction;
- fact-to-rule benchmark;
- temporal cases;
- jurisdiction cases;
- ambiguity classification.

Exit criteria:
- retrieval quality and legal understanding reported independently.

## Stage 8 — Knowledge/version intelligence

Implement:
- LegalVersion;
- amendment relationships;
- effective periods;
- release manifests;
- atomic publish/rollback;
- historical as-of retrieval.

Exit criteria:
- historical and current law cannot be silently mixed.

## Stage 9 — Grounded Legal Research MVP

First customer workflow:

```text
Question
→ structured understanding
→ evidence retrieval
→ evidence report
→ grounded answer
→ citations
→ uncertainty/conflict
```

Acceptance is measured by expert review and user task performance.

## Stage 10 — Conflict intelligence + constrained agents

Implement only after reliable evidence and legal understanding exist.

Agents must operate through explicit tools/contracts and remain evidence-constrained.

## Stage 11 — Productization

Introduce:
- authentication;
- multi-tenancy;
- API quotas;
- audit;
- SaaS workflows;
- private deployment;
- data residency;
- billing/usage accounting.

## Stage 12 — Jurisdiction packs

Egypt remains the first pack.

Each new jurisdiction requires its own:
- corpus;
- authority policy;
- temporal model;
- terminology tests;
- benchmark;
- legal review;
- release identifier.

## Training decision gate

Fine-tuning/SFT is allowed only after measured failure analysis shows retrieval/evidence/system prompting cannot reasonably solve the target failure and the dataset is licensed and separated correctly.

Ordinary legal updates should use versioned knowledge releases, not routine base-model retraining.

## Merge policy

No substantial stage is complete until:
- required tests pass;
- relevant benchmarks pass;
- resource limits are known;
- Claude review findings are resolved or explicitly accepted;
- documentation/decision records are updated.
