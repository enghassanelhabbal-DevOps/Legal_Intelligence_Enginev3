# Legal Intelligence Engine — Foundation Index

Repository: https://github.com/enghassanelhabbal-DevOps/Legal_Intelligence_Enginev3

Active engineering branch: `feat/enterprise-foundation`

`ARCHITECTURE_CONTRACT.md` is the authoritative architecture contract.

## Read order

1. `ARCHITECTURE_CONTRACT.md` — architecture, product direction, invariants, stage boundaries.
2. `CLAUDE.md` — implementation/review rules for Claude Code and engineering agents.
3. `COPILOT.md` — concise coding-agent rules.
4. `docs/REPOSITORY_STRUCTURE.md` — canonical repository layout and cleanup rules.
5. `docs/PRODUCT_REQUIREMENTS.md` — product scope, users, workflows, acceptance criteria, non-goals.
6. `docs/LEGAL_DOMAIN_SPEC.md` — legal semantics, authority, jurisdiction, temporal behavior.
7. `docs/DATA_GOVERNANCE.md` — dataset intake, provenance, licensing, leakage and releases.
8. `docs/EVALUATION_SYSTEM_SPEC.md` — benchmark tracks, metrics and release gates.
9. `docs/RESOURCE_RELIABILITY_SPEC.md` — resource budgets, recovery and failure learning.
10. `docs/SECURITY_PRIVACY_SPEC.md` — trust boundaries, secrets, privacy and abuse resistance.
11. `docs/SYSTEM_COMPONENT_SPEC.md` — component ownership and dependency boundaries.
12. `docs/DELIVERY_STAGE_PLAN.md` — stage sequencing and definition of done.
13. `docs/ENGINEERING_GOVERNANCE.md` — engineering process and review discipline.
14. `docs/ENGINEERING_DECISION_REGISTER.md` — durable architectural decisions.
15. `docs/CLAUDE_STAGE_HANDOFF_TEMPLATE.md` — reusable stage review handoff.
16. `docs/CLAUDE_EXECUTION_MASTER.md` — current Stage 1 completion/cleanup execution brief.

## Supporting documentation

- `docs/runbooks/` — operational setup/deployment/runtime guidance.
- `docs/research/` — active corpus/research investigations only.
- `artifacts/reports/` — measured reports and reproducible benchmark outputs.

Historical architecture drafts and promotion patches are intentionally removed from the working tree after promotion. Git history is the archive.

## Truth model

Every project claim must be classified as one of:

- **Verified** — reproduced by current code/tests/benchmarks/artifacts.
- **Required** — contractually required before the relevant release gate.
- **Planned** — intentionally deferred capability.

A classifier prediction is not verified legal truth. A parser miss is not proof that legal structure is absent. A successful model call is not proof of legal correctness.

## Current stage

The project is completing **Stage 1 — Dataset Intake + Evaluation Foundation**.

Primary objectives:

- legal-resource/document-type representation;
- source/provenance handling;
- structure parsing;
- exact duplicate clustering without provenance loss;
- leakage-safe grouping;
- dataset manifests and reports;
- independent evaluation preparation;
- manual-gold validation design.

No fine-tuning or broad retrieval optimization is authorized by Stage 1.

## Current protected truth

The historical `MRR=0.835` value is an **UNVERIFIED HISTORICAL REFERENCE** unless an authoritative reproducible harness is restored.

The current BM25 self-retrieval smoke benchmark is a regression guard only, not evidence of Egyptian legal understanding.

Full dense + BM25 + reranker production-path benchmarking belongs to Stage 4.

## Engineering loop

```text
Requirement
  -> architecture/decision
  -> smallest coherent implementation
  -> focused tests
  -> integration/regression tests
  -> lint/type checks
  -> relevant benchmark/resource measurement
  -> adversarial review
  -> project-owner decision
  -> authorized fixes
  -> re-test/re-benchmark
  -> documentation/decision record
  -> release decision
```

## Conflict rule

When authoritative documents disagree, stop and resolve the contradiction. Never silently select the most convenient interpretation.
