# Claude Stage Handoff Template

> Use this file as the standard handoff format for every substantial implementation stage.

## Stage

- Stage ID:
- Title:
- Target branch:
- Base commit:
- Date:

## Objective

Describe the engineering/product problem in one paragraph.

## Why now

What evidence or requirement makes this stage necessary?

## Scope

### In scope
- 

### Out of scope
- 

## Contract references

- `CLAUDE.md`
- `ARCHITECTURE_CONTRACT.md` or approved draft
- relevant foundation specification
- relevant decision records

## Current implementation truth

List only verified facts from the repository and measured reports.

## Desired behavior

State observable behavior, interfaces, and acceptance criteria.

## Constraints

### Correctness
- no unsupported legal semantics;
- no benchmark contamination;
- no silent jurisdiction/version mixing.

### Resources
- CPU budget:
- RAM budget:
- VRAM budget:
- latency target/measurement plan:

### Compatibility
- Python/runtime:
- OS:
- API compatibility:

## Required implementation approach

1. Inspect existing implementation before adding modules.
2. Prefer the smallest coherent change.
3. Reuse canonical contracts.
4. Add tests before or with behavior changes.
5. Add telemetry where appropriate.
6. Do not modify unrelated subsystems.

## Test plan

- unit tests:
- integration tests:
- negative/failure tests:
- security tests:

## Benchmark plan

- dataset version:
- knowledge release:
- baseline:
- metrics:
- resource measures:

## Claude adversarial review checklist

Claude must challenge:

- architecture boundary violations;
- hidden duplicate logic;
- data leakage;
- legal semantic assumptions;
- incorrect citations/provenance;
- temporal/jurisdiction bugs;
- security boundaries;
- resource regressions;
- error handling and retry loops;
- portability;
- unnecessary dependencies;
- future migration/scalability implications.

## Review output required

Claude should return:

```text
Verdict: APPROVE / APPROVE-WITH-FIXES / BLOCK

Critical findings
High findings
Medium findings
Low findings

Correctness assessment
Architecture assessment
Data/evaluation assessment
Security assessment
Resource assessment
Test assessment
Future-compatibility assessment

Required changes
Optional improvements
Evidence/commands used
```

## Change authorization boundary

Claude may review and recommend fixes. Production changes are made only through the explicitly authorized implementation step. Review and implementation must remain auditable and reproducible.

## Completion record

- files changed:
- tests:
- benchmark:
- resource report:
- Claude verdict:
- findings resolved:
- remaining accepted risks:
- release decision:
