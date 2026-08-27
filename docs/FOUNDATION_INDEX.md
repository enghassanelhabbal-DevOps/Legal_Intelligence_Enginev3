# Legal Intelligence Engine — Foundation Documentation Index

> Status: Working foundation set for `feat/enterprise-foundation`.
> The authoritative architecture remains `ARCHITECTURE_CONTRACT.md` until V4 is explicitly promoted.
> These documents define implementation guidance, evaluation policy, data governance, reliability, product scope, and stage execution.

## Purpose

This directory is the operating system for building the Legal Intelligence Engine as a production-grade Legal AI platform rather than a demo chatbot.

## Document hierarchy

1. `ARCHITECTURE_CONTRACT.md` — authoritative technical contract after approval.
2. `CLAUDE.md` — implementation/review instructions for Claude Code and coding agents.
3. `ARCHITECTURE_CONTRACT_V4_RECONCILED_DRAFT.md` — proposed contract awaiting final approval.
4. `PRODUCT_REQUIREMENTS.md` — product scope, users, workflows, acceptance criteria, and non-goals.
5. `LEGAL_DOMAIN_SPEC.md` — legal semantics, jurisdictions, temporal law, authority, and answer behavior.
6. `DATA_GOVERNANCE.md` — dataset intake, provenance, licensing, quality, leakage, and release policy.
7. `EVALUATION_SYSTEM_SPEC.md` — evaluation tracks, benchmarks, datasets, metrics, and quality gates.
8. `RESOURCE_RELIABILITY_SPEC.md` — resource budgets, adaptive execution, fault handling, and failure learning.
9. `SECURITY_PRIVACY_SPEC.md` — threat model, trust boundaries, secrets, data isolation, and abuse resistance.
10. `DELIVERY_STAGE_PLAN.md` — staged implementation plan and definition of done.
11. `ENGINEERING_DECISION_REGISTER.md` — durable decisions and their rationale.
12. Existing runbooks and reviews — deployment and implementation details.

## Current truth vs target truth

The project MUST distinguish three states:

- **Verified:** behavior measured in the current code/repository.
- **Required:** architectural or product behavior that must exist before a release gate can pass.
- **Planned:** future capability that is intentionally deferred.

A planned capability is never presented as implemented.

## Development loop

```text
Requirement
  -> Architecture decision
  -> Small implementation step
  -> Tests
  -> Benchmark
  -> Resource measurement
  -> Claude adversarial review
  -> Fix findings
  -> Re-test
  -> Decision record
  -> Release
```

## Primary objective

Build an evidence-first, jurisdiction-aware, version-aware, resource-efficient legal intelligence system that starts with Egyptian law and can later support explicit GCC/MENA jurisdiction packs.

## First product wedge

Egyptian legal research + evidence reports for professional users.

## First technical objective

Create a trustworthy evaluation and data foundation before training/fine-tuning or adding agentic complexity.

## Current protected truth

The historical `MRR=0.835` hybrid figure is treated as an **unverified historical reference** unless a reproducible harness is restored. The CI smoke baseline is useful as a regression guard but is not proof of legal understanding. The full dense+BM25+reranker pipeline must receive its own reproducible benchmark before its quality is claimed.

## Review ownership

- Architecture and product intent: project owner + architecture review.
- Implementation and adversarial code review: Claude Code.
- Measured truth: tests, benchmarks, CI artifacts, and reproducible reports.
- Legal semantic validation: domain-expert review where required.

## Rule

When two documents disagree, stop and resolve the contradiction. Never silently choose whichever document is convenient.