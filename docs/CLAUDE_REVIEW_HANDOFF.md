# Claude Review Handoff — Legal Intelligence Engine

Use this document as the mandatory handoff context for Claude Code before implementing or approving a material change.

## Mission

Turn the existing v3 repository into a trustworthy, resource-efficient, jurisdiction-aware Legal Intelligence Platform focused first on Egyptian Arabic legal intelligence, with a future path to MENA and global deployments.

## Current architectural principles

- The legal knowledge base is authoritative; LLM weights are replaceable.
- Retrieval, reranking, evidence, generation, evaluation, and deployment remain separate concerns.
- No jurisdiction mixing unless explicitly requested.
- No silent mixing of legal versions across time.
- Every material legal claim must be traceable to retrieved evidence.
- Production failures never directly self-modify code, prompts, models, or legal knowledge.
- Failure learning is controlled: classify -> recover -> record -> regression case -> fix -> benchmark -> review -> release.
- Resource use is budgeted and hardware-aware; CPU-only remains a valid execution mode.
- Do not trade legal correctness for raw latency or benchmark score without an explicit documented decision.

## Evaluation philosophy

The existing retrieval numbers are protected regression baselines, but the current self-retrieval smoke set is not sufficient to prove legal understanding. New evaluation must distinguish:

1. Retrieval quality
2. Multi-evidence / full recall
3. Query understanding
4. Legal entailment / groundedness
5. Arabic legal reasoning
6. Abstention / insufficient-evidence behavior
7. Temporal and jurisdiction correctness
8. Citation validity
9. Resource efficiency
10. End-to-end user task success

Never train and evaluate on overlapping examples without a documented leakage analysis.

## Dataset intake requirements

Every new dataset must be profiled before training or indexing:

- source and provenance;
- license/usage constraints;
- schema and field semantics;
- language/dialect;
- jurisdiction;
- legal domains;
- temporal coverage;
- duplicate rate;
- contamination/leakage risk;
- label quality and agreement if available;
- task suitability;
- recommended role: knowledge, train, validation, test, benchmark, or adversarial.

## Claude review output

Return exactly:

### Verdict
APPROVE / APPROVE WITH CHANGES / REQUEST CHANGES

### Blocking findings
Correctness, legal-data integrity, security, reliability, benchmark validity, or serious performance regressions.

### Architecture
Dependency violations, duplicated business logic, incorrect ownership, unnecessary coupling, premature microservices.

### ML / IR
Retrieval correctness, candidate preservation, ranking behavior, leakage, metric validity, Arabic normalization, query understanding, reranking, evidence selection.

### Resource profile
CPU, RAM, VRAM, thread/process count, model residency, batch behavior, latency, estimated API cost, fallback/degradation behavior.

### Security
Secrets, prompt injection, untrusted documents, tenant isolation, authorization, auditability, unsafe tool access.

### Tests to add
Name the exact test module and scenario for every missing test.

### Regression risks
Describe likely future breakages and what telemetry or gate should catch them.

### Acceptance criteria
List measurable conditions required before merge.

## Hard prohibitions

- No broad rewrite when an incremental change can solve the problem.
- No new dependency without justification.
- No claim of improved accuracy without a before/after benchmark.
- No claim of production readiness without evidence.
- No direct use of hidden chain-of-thought.
- No use of generated legal text as authoritative source data.
