# ARCHITECTURE CONTRACT V4 — PROMOTION PATCH

Status: REQUIRED BEFORE PROMOTION
Target: `ARCHITECTURE_CONTRACT_V4_RECONCILED_DRAFT.md`

This patch closes the final review finding identified by the second-round/final promotion review. Apply these edits to the reconciled draft before promoting it to `ARCHITECTURE_CONTRACT.md`.

## 1. Section 5 — Known gaps

The current list must contain six items. Keep the existing five items and add this exact item:

> 6. The current primary Gemini integration is vendored in the root `app.py`, independently implementing provider-specific generation/retry/fallback behavior instead of using the canonical generation adapter layer. This is a known generation-layer duplication gap; it is tracked by DR-013/DR-014 and must be removed during Stage 3 after parity validation.

The paragraph after the list remains:

> These gaps are tracked implementation work, not reasons to rewrite the repository.

## 2. Section 32 — No-Duplicate Implementation Rule

The section must explicitly identify both known root-entrypoint violations. Retain the retrieval wording and add the following generation wording immediately beside it:

> The existing root `app.py` generation path is also a known technical-debt item: Gemini provider logic, retry/backoff, model-variant fallback, timeout handling, and response normalization are currently implemented outside `src/legal_ai/generation`. This duplication must be migrated to the canonical `GeminiBackend` and `GenerationManager` path before the root implementation is removed.

Also retain/strengthen the general rule:

> Any new capability introduced first in `app.py` for deployment convenience is presumptively a duplicate-implementation violation unless it is presentation-only or has a named, testable migration path back to the canonical `src/legal_ai` layer.

## 3. Section 33 — Known-Limitation Register

Add a row matching the existing retrieval technical-debt row:

| Gap | Current state | Exit condition | Target stage |
|---|---|---|---|
| Root `app.py` duplicate generation (Gemini) | Primary Gemini generation/retry/fallback logic exists outside `src/legal_ai/generation` | Canonical `GeminiBackend` provides behavior parity under the same contracts; integration tests and provider-path benchmarks pass; root Gemini implementation is deleted | Stage 3 |

The register must make clear that the root `app.py` retrieval duplication and root `app.py` Gemini generation duplication are two separate migration items under the same canonicalization stage.

## 4. Section 34 — Stage 3

Stage 3 must be the canonical consolidation + fault intelligence stage and must explicitly contain all of the following work items:

- remove root `app.py` duplicate retrieval/business logic;
- implement/canonicalize `GeminiBackend` under `src/legal_ai/generation/backends/`;
- migrate Gemini provider behavior from `app.py` with behavioral parity for retry/backoff, model-variant fallback, timeout/error mapping, and response normalization;
- run parity/integration tests before deleting the vendored Gemini implementation;
- remove root `app.py` duplicate Gemini generation logic;
- implement fault taxonomy, recovery policy, graceful degradation, failure fingerprinting, and regression-case export.

Stage 3 exit criteria must include:

- exactly one canonical retrieval/business-logic path;
- exactly one canonical generation/provider-adapter path;
- Gemini is served through the canonical generation abstraction;
- no production dependency on vendored retrieval or Gemini provider code in root `app.py`;
- failure/recovery behavior is bounded, observable, deterministic, and reversible.

## 5. Stage / dependency interpretation

This patch does not change the previously approved stage ordering:

```text
Stage 10 — Jurisdiction Expansion
Stage 11 — Commercial / Productization
```

The jurisdiction-first-before-commercial decision remains authoritative.

## 6. Promotion verification checklist

Claude must confirm all of the following before approving promotion:

- [ ] Section 5 names both retrieval and Gemini generation duplication.
- [ ] Section 32 names both violations and contains the general `app.py` presumptive-duplication rule.
- [ ] Section 33 contains a Gemini duplication row with Stage 3 exit criteria.
- [ ] Section 34 Stage 3 includes retrieval consolidation + Gemini migration/removal + fault intelligence.
- [ ] `DELIVERY_STAGE_PLAN.md` and Section 34 have identical stage ordering and Stage 3 intent.
- [ ] `ENGINEERING_DECISION_REGISTER.md` contains DR-013 and DR-014 referenced by this patch.
- [ ] `SYSTEM_COMPONENT_SPEC.md` names `GeminiBackend` and the provider data boundary.
- [ ] No statement in the contract presents an unverified Gemini or retrieval metric as a current measured claim.
- [ ] Promotion preserves the distinction between Verified, Required, and Planned behavior.

## 7. Important implementation boundary

Applying this patch to the architecture contract is documentation work only. It does NOT authorize automatic runtime self-modification and does NOT authorize deleting `app.py` logic until Stage 3 parity tests and benchmarks pass.

The sequence remains:

```text
Contract promotion
    -> Stage 3 design
    -> GeminiBackend implementation
    -> parity tests
    -> retrieval/generation benchmark
    -> Claude adversarial review
    -> human/project-owner authorization
    -> delete legacy paths
    -> re-test
```
