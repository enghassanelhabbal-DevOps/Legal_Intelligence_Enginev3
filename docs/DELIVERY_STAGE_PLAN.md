# Delivery Stage Plan

## Status and authority

Status: approved working execution plan candidate for `feat/enterprise-foundation`.

This plan is subordinate to `ARCHITECTURE_CONTRACT.md` until V4 is explicitly promoted. It must remain stage-for-stage consistent with the architecture contract. If the two disagree, stop and reconcile before implementation.

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
→ Human/project-owner decision
→ Authorized implementation/fix
→ Re-test
→ Record
→ Release
```

## Stage 0 — Contract and foundation reconciliation

Status: review / gate.

Outputs:
- approved architecture contract;
- approved Claude instructions;
- foundation document index;
- decision register;
- verified-vs-required-vs-planned inventory;
- cross-document consistency check;
- known technical-debt register.

Exit criteria:
- no contradiction between authoritative and execution documents;
- baseline status explicitly classified;
- current known gaps documented;
- no undocumented production-path duplication remains as an architectural surprise;
- Claude final review has no unresolved material blocker.

## Stage 1 — Data intake + evaluation foundation

Goal: make datasets measurable, versioned, provenance-aware, and leakage-safe inputs.

Implement:
- dataset manifest schema;
- intake/profiling CLI;
- provenance/license fields;
- schema validation;
- language/jurisdiction metadata;
- legal-time metadata where available;
- duplicate/near-duplicate checks;
- leakage/contamination checks;
- task-role classification;
- versioned split manifest;
- benchmark manifest;
- dataset quality report.

Exit criteria:
- current 952-article corpus can be profiled;
- second dataset can be profiled without custom pipeline code;
- held-out benchmark is isolated;
- reports are reproducible;
- no final benchmark is consumed by training, tuning, prompt selection, threshold selection, or model selection.

## Stage 2 — Canonical runtime/resource foundation

Goal: portable, bounded, observable execution.

Implement:
- hardware discovery;
- CPU/RAM/VRAM resource profiles;
- bounded workers/queues;
- timeout/retry policies;
- model residency policy;
- lightweight resource telemetry;
- adaptive batch policy;
- remote-LLM execution profile;
- CPU-minimal execution profile.

Exit criteria:
- CPU-minimal and remote-LLM paths work;
- constrained GPU path has measured limits or an explicitly documented unverified status;
- no unbounded retry/spawn behavior;
- resource policy is centralized and not duplicated in model backends.

## Stage 3 — Canonical pipeline consolidation + fault intelligence

Goal: eliminate production-path duplication while making failure behavior bounded, observable, and recoverable.

Canonical consolidation work:
- remove/retire retrieval business logic vendored in root `app.py`;
- remove/retire generation business logic vendored in root `app.py`;
- add the Gemini provider as a canonical `LLMBackend` implementation under `src/legal_ai/generation/backends/`;
- preserve existing Gemini behavior through parity tests before deleting the vendored implementation;
- make the canonical Streamlit path call `QueryService`/canonical adapters in both remote and embedded modes;
- maintain a documented migration/deprecation boundary for any temporary compatibility shim.

Fault intelligence work:
- error taxonomy;
- normalized `FailureEvent`;
- recovery policies;
- graceful degradation;
- bounded retry/backoff;
- failure fingerprint;
- regression-case export;
- failure/recovery telemetry.

Exit criteria:
- root `app.py` contains no retrieval or generation business implementation;
- Gemini is served through the canonical generation adapter;
- old and new Gemini paths pass parity tests for supported behaviors before retirement;
- injected failures produce deterministic bounded recovery;
- failures remain observable;
- no production self-modification.

## Stage 4 — Full production retrieval benchmark

Goal: replace smoke-only confidence with realistic measurement of the exact production retrieval path.

Owner/trigger:

This benchmark is the mandatory retrieval-quality gate for the production stack and must be established in Stage 4 before claiming optimization of the full dense + lexical + reranker pipeline.

Implement:
- expert-labeled query set;
- realistic user-style queries;
- multi-evidence gold sets;
- paraphrase sets;
- Arabic robustness sets;
- jurisdiction-confusion cases;
- temporal cases;
- insufficient-evidence cases;
- candidate recall reporting;
- full dense + BM25 + reranker benchmark;
- category-level error analysis.

Exit criteria:
- full production retrieval path benchmarked;
- metrics reproducible;
- candidate recall and final evidence recall are reported;
- category-level error analysis is available;
- baseline is versioned and attributable to exact code/config/data artifacts.

## Stage 5 — Retrieval/reranker optimization

Only after Stage 4.

Experiments may cover:
- query expansion;
- normalization variants;
- candidate count;
- fusion methods;
- reranker models;
- batch size;
- score calibration;
- latency/quality tradeoffs.

Acceptance requires quality/resource evidence and must not weaken the protected benchmark without an explicit documented decision.

## Stage 6 — Evidence enforcement

Goal: make evidence a hard correctness boundary.

Implement:
- `EvidenceItem`;
- `EvidenceSet`;
- claim-to-evidence mapping;
- support classification;
- citation validation;
- evidence sufficiency gate;
- conflict flags;
- grounded-context contract.

Exit criteria:
- generation cannot bypass evidence validation;
- unsupported material claims are failures;
- evidence IDs and source provenance remain traceable end-to-end.

## Stage 7 — Legal understanding benchmark + query understanding

Implement:
- `QueryRequest` / `QueryUnderstanding` / `RetrievalPlan` contracts;
- issue/rule/condition/exception extraction;
- fact extraction relevant to a legal rule;
- fact-to-rule benchmark;
- temporal cases;
- jurisdiction cases;
- ambiguity classification;
- user-style Arabic legal paraphrase benchmark.

Exit criteria:
- retrieval quality and legal understanding are reported independently;
- evaluation distinguishes retrieval failure from reasoning failure.

## Stage 8 — Knowledge/version intelligence

Implement:
- `LegalVersion`;
- amendment relationships;
- effective periods;
- repeal/supersession relationships;
- authority metadata;
- release manifests;
- atomic publish/rollback;
- historical as-of retrieval.

Exit criteria:
- historical and current law cannot be silently mixed;
- every query can identify the knowledge release/version scope used.

## Stage 9 — Grounded Egyptian Legal Research MVP

First customer workflow:

```text
Question
→ structured understanding
→ jurisdiction/time scope
→ evidence retrieval
→ evidence report
→ grounded legal analysis
→ citations
→ uncertainty/conflict
→ safe answer or abstention
```

Acceptance:
- expert legal review;
- user task performance;
- citation/support accuracy;
- abstention behavior;
- measured latency/resource cost.

## Stage 10 — Jurisdiction expansion foundation

Goal: prove that the architecture can add jurisdictions without contaminating Egyptian-law semantics.

Initial expansion candidates are explicit jurisdiction packs (for example GCC/MENA), but no jurisdiction is enabled merely by adding documents to the shared corpus.

Implement only the reusable jurisdiction-pack contract:
- jurisdiction manifest;
- authority policy;
- corpus boundary;
- terminology profile;
- temporal model;
- benchmark set;
- legal-review checklist;
- release identifier;
- cross-jurisdiction isolation tests.

Exit criteria:
- at least one additional jurisdiction can be represented as an isolated versioned pack;
- cross-jurisdiction retrieval behavior is explicitly tested;
- existing Egypt benchmark performance is not silently changed by the new pack.

## Stage 11 — Commercial platform / productization

Introduce, based on validated customer demand:
- authentication;
- authorization;
- multi-tenancy;
- API quotas;
- structured audit;
- usage accounting;
- SaaS workflows;
- private deployment;
- data residency controls;
- enterprise governance;
- billing integration where justified.

Exit criteria:
- tenant/data isolation is tested;
- security boundaries are explicit;
- usage and cost can be measured;
- production deployment has rollback and audit capability.

## Training decision gate

Fine-tuning/SFT is allowed only after measured failure analysis shows that retrieval, evidence selection, query understanding, system prompting, or deterministic domain logic cannot reasonably solve the target failure and the dataset is licensed, high quality, leakage-safe, and suitable for the task.

Training decisions must identify:
- target capability;
- dataset role;
- expected metric improvement;
- resource budget;
- deployment effect;
- rollback path.

Ordinary legal updates should use versioned knowledge releases, not routine base-model retraining.

## Security staging

Security controls are staged, not deferred wholesale:

- Stage 0–1: secrets hygiene, schema validation, safe file handling, provenance/license checks, basic size/type limits, benchmark-data isolation.
- Stage 2–3: bounded retries/queues, prompt-injection boundary, structured error handling, safe remote-provider configuration, no credential leakage.
- Stage 4–6: citation/evidence integrity, abuse-resistant benchmark endpoints, rate limiting where exposed.
- Stage 7–9: authentication/authorization boundaries for product workflows, audit events for important legal operations.
- Stage 10: cross-jurisdiction isolation and pack-level data controls.
- Stage 11: tenant isolation, enterprise audit, data residency, retention/deletion controls, enterprise identity/SSO.

## Merge policy

No substantial stage is complete until:
- required tests pass;
- relevant benchmarks pass or the stage explicitly records an unverified gap;
- resource limits are known or documented as outstanding;
- Claude review findings are resolved or explicitly accepted by the project owner;
- any requested implementation change happens in an authorized implementation step after review;
- documentation/decision records are updated;
- no new document contradiction is introduced.
