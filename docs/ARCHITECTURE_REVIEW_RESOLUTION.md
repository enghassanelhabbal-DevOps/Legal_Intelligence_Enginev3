# Architecture Review Resolution — V4 Reconciled Draft

> Status: Review-resolution record. This document records the disposition of findings raised during adversarial review of `ARCHITECTURE_CONTRACT_V4_RECONCILED_DRAFT.md`.
>
> It is not the architecture contract itself. It becomes historical evidence for why the contract was changed or why a gap was intentionally staged.

## 1. Review outcome

The second-round review confirms that the V4 reconciliation correctly resolved the previous five material findings:

1. Unverified historical retrieval baseline is no longer presented as a current product metric.
2. Root `app.py` retrieval duplication is explicitly recognized as technical debt with an exit condition.
3. First-class contracts are staged rather than being a Stage-1 blanket requirement.
4. M2200 GPU measurements are explicitly treated as an outstanding benchmark gap.
5. Claude review is separated from authorization to implement review findings.

The second-round review identifies one new material architectural gap and two lower-severity staging gaps.

## 2. Material finding — duplicated Gemini generation path

### Finding

The production-facing root `app.py` contains a substantial Gemini implementation independent of `src/legal_ai/generation`.

The canonical generation layer currently contains:

- `qwen_transformers_backend.py`
- `openai_compatible_backend.py`

The root Streamlit application also contains a separate Gemini integration, including model discovery, provider invocation, retries, and fallback behavior.

### Architectural consequence

This violates the intended invariant of one canonical generation adapter layer and creates the same class of drift already identified in retrieval duplication.

This creates concrete risks:

- provider behavior diverges between deployment modes;
- retry/fallback logic is duplicated;
- fixes can land in one path but not the other;
- benchmarked behavior may not match production behavior;
- security and timeout policy may diverge;
- resource accounting becomes incomplete;
- provider switching becomes harder;
- future multi-provider routing becomes inconsistent.

### Required resolution

The canonical architecture shall be:

```text
UI / API
   -> QueryService
      -> Generation Manager
         -> LLMBackend protocol
            -> provider backend
```

Gemini must be implemented behind the canonical generation abstraction. The root `app.py` provider implementation must then be retired.

### Acceptance criteria

The finding is closed only when:

- a Gemini backend exists under the canonical generation package;
- retry/fallback policy is represented in the canonical provider/runtime design rather than duplicated in the UI;
- root `app.py` contains no provider-specific LLM orchestration;
- remote/embedded modes execute the same generation implementation;
- provider behavior is covered by focused tests;
- Gemini-specific functionality has parity tests against the existing production behavior;
- latency, error rate, and resource impact are measured before/after migration;
- the migration does not reduce existing grounded-generation safety guarantees.

## 3. Full retrieval benchmark gap

The production retrieval path must eventually be benchmarked as a complete pipeline:

```text
Dense retrieval
 + lexical retrieval
 -> candidate union/filtering
 -> reranker
 -> evidence selection
```

The current CI smoke gate is not sufficient evidence for this pipeline because it exercises a simpler retrieval path.

### Required stage

This is explicitly a **Stage 4** obligation in the delivery roadmap.

It does not block Stage 1 data/evaluation foundation work unless Stage 1 changes make comparison impossible.

## 4. Security staging clarification

Security controls are split by implementation maturity.

### Stage 0 / immediate

- secrets hygiene;
- schema/input validation;
- safe file paths;
- request size limits;
- basic error sanitization;
- no credentials in source control;
- untrusted-content boundaries.

### Stage 1–3

- dataset provenance validation;
- retrieval/evidence prompt-injection boundaries;
- structured output validation;
- provider/API timeout and retry safety;
- rate limiting on public-facing endpoints where applicable;
- security-focused regression tests.

### Stage 6+

- expanded audit trails;
- authentication and authorization hardening;
- tenant-aware data handling;
- enterprise policy enforcement.

### Stage 11

- full tenant isolation;
- enterprise data governance;
- deployment-specific data residency controls;
- enterprise identity/SSO integration;
- contractual security controls.

## 5. Root `app.py` standing rule

The architecture now adopts the following standing rule:

> Any new capability introduced directly into root `app.py` for deployment convenience is presumed to be a duplicate-implementation violation unless it is presentation-only or has an explicit, documented migration path into the canonical domain layer.

Deployment constraints do not override domain boundaries.

## 6. Review decision

### V4 promotion status

**Not yet promoted.**

Promotion requires at least:

- the Gemini duplication issue to be explicitly incorporated into the contract;
- the staged security wording to be incorporated;
- the full-pipeline benchmark obligation to be tied to Stage 4;
- Claude final adversarial review of the resulting document;
- project-owner approval.

### Important distinction

Promotion of the architecture contract does **not** require every future capability to already exist in code.

The contract is allowed to contain staged requirements when each requirement has:

- a defined purpose;
- a named stage;
- acceptance criteria;
- a measurable exit condition;
- no implication that it is already implemented.

## 7. No-code rule while architecture is unresolved

Until V4 is promoted:

- no new major feature work should depend on disputed architecture assumptions;
- no fine-tuning should begin;
- no production agent layer should be introduced;
- no jurisdiction expansion should begin;
- no irreversible data migration should begin.

Safe preparatory work may continue where it does not depend on unresolved contracts.
