# Claude Execution Master — Stage 1 Completion + Repository Cleanup

Repository: https://github.com/enghassanelhabbal-DevOps/Legal_Intelligence_Enginev3

Required branch: `feat/enterprise-foundation`

## Role

Act as Principal Software Architect, Principal Python Engineer, Legal-NLP/IR Engineer, Data/Evaluation Engineer, Reliability Engineer, Security Engineer, and adversarial reviewer.

This is a real Legal Intelligence Platform, not a demo RAG application. Optimize for legal fidelity, clean architecture, auditability, measurable quality, resource efficiency, portability, and long-term maintainability.

## Mandatory startup procedure

1. Clone/fetch the repository from the exact URL above.
2. Checkout `feat/enterprise-foundation`.
3. Run `git status`, `git branch --show-current`, and `git log -5 --oneline`.
4. Reconcile any local/unpushed work before editing. Do not overwrite valuable local Stage 1 changes.
5. Read, in order:
   - `ARCHITECTURE_CONTRACT.md`
   - `CLAUDE.md`
   - `COPILOT.md`
   - `docs/FOUNDATION_INDEX.md`
   - `docs/REPOSITORY_STRUCTURE.md`
   - `docs/PRODUCT_REQUIREMENTS.md`
   - `docs/LEGAL_DOMAIN_SPEC.md`
   - `docs/DATA_GOVERNANCE.md`
   - `docs/EVALUATION_SYSTEM_SPEC.md`
   - `docs/RESOURCE_RELIABILITY_SPEC.md`
   - `docs/SECURITY_PRIVACY_SPEC.md`
   - `docs/SYSTEM_COMPONENT_SPEC.md`
   - `docs/DELIVERY_STAGE_PLAN.md`
   - `docs/ENGINEERING_DECISION_REGISTER.md`
6. Inspect the real code and tests before proposing changes.

If documentation conflicts with code, distinguish verified behavior from required architecture. If authoritative documents conflict with one another, stop and report the contradiction before implementation.

## Immediate mission

Complete Stage 1 Dataflare foundation and leave the repository in a clean, professional, future-proof state.

The currently analyzed Dataflare file is associated with SHA-256:

`a55c349e9c95faffcdf49b66c726be7ae4ed738aafd43767d8ae99f5903d4458`

Measured corpus facts that must be reproduced from the exact file before being treated as current truth:

- 2,434 records
- 25,054,372 tokens
- 171 unique category values
- flattened text with no internal newlines in the analyzed revision
- heterogeneous legal material, not a homogeneous statute corpus
- approximately 2,110 case-law-like records by structural signals; do not relabel all as Court of Cassation
- approximately 94.7–94.8% judicial citation extraction coverage; this is coverage, not accuracy
- 347 exact-text duplicate clusters / 696 participating rows; do not interpret 696 as removable rows
- Unicode NFC resolves the observed decomposed Arabic hamza cases before Arabic-specific retrieval normalization

Reproduce metrics from code. Never copy them blindly into claims.

## Stage 1 required canonical contracts

Keep the implementation minimal and compositional. Reuse existing contracts if already present.

Required concepts include:

- `DocumentType`
- `LegalResourceIdentity`
- legislative identity shape
- judicial identity shape
- `SourceProvenance`
- `JudicialCitation`
- `DuplicateCluster`
- `DatasetManifest`
- leakage/grouping identity
- `EvaluationCase`

Do not introduce a deep inheritance hierarchy if tagged composition is simpler.

## Document-type policy

Support a controlled vocabulary capable of distinguishing at least:

- statute
- regulation
- constitutional material
- civil cassation
- criminal cassation
- administrative judiciary
- other judicial material
- international instrument
- legal form/template
- commentary
- academic material
- mixed
- unknown/invalid

Classifier outputs are predictions, not legal truth. Report distribution as `classified_as`, not verified corpus composition, until a manually reviewed gold sample exists.

## Legal-structure policy

Raw source text is immutable authority input.

Canonical legal structure and retrieval chunks are different objects.

Support strategy-based parsing rather than one giant regex. At minimum reason about:

- inline `مادة` article markers
- ordinal article headings
- flattened single-paragraph statutes
- zero-padded numeric article formats such as 001/002/003
- table-like `رقم المادة / الموضوع / نص المادة` formats
- referential mentions such as `طبقاً للمادة 5` that must not create false article boundaries
- judicial citation structures
- forms/commentary where no statutory structure should be fabricated

A parser miss is not proof that a record has no legal structure. Label it as parser non-detection until independently reviewed.

## Unicode/Arabic policy

Required flow:

`raw_text -> Unicode NFC -> Arabic retrieval normalization`

NFC and Arabic normalization are separate responsibilities.

Preserve raw source text. Add explicit tests for decomposed hamza, alef variants, ya/alif-maqsura, diacritics, tatweel, punctuation, and mixed Arabic/English.

## Duplicate policy

Never blindly delete duplicate-text rows.

Model exact duplicates as clusters with canonical content plus source membership/provenance.

Distinguish:

- exact-text duplicate
- metadata variant
- source variant
- possible version variant
- near duplicate
- unknown relationship

`exact text + no detected metadata variance` does not automatically mean legally safe deletion. Preserve traceability.

## Judicial grouping/leakage policy

Do not group judicial records using topic labels or `law_name` alone.

Prefer case/citation identity such as appeal number, judicial year, court/system, date, and duplicate cluster where available.

For legislation, prefer instrument/law/version/source grouping.

Never use random row-level splitting when related legal material could cross splits.

## Stage 1 materialization gate

Stage 1 is NOT complete until the repository produces versioned, machine-readable artifacts for the exact Dataflare revision.

Create at minimum:

- `artifacts/datasets/dataflare_egypt_legal_corpus_v1/manifest.json`
- `artifacts/datasets/dataflare_egypt_legal_corpus_v1/split_manifest.json` or a better canonical equivalent
- `artifacts/reports/dataflare_corpus_report_v1.json`

The manifest must include dataset identity, file hash, schema, record/token counts, source/license/provenance state, classifier distribution, category distribution, duplicate-cluster statistics, Unicode profile, structural parser profile, parser/classifier versions, software commit, and generation timestamp where appropriate.

For Stage 1, prefer role partitions such as:

- knowledge
- development
- protected evaluation candidates
- manual review
- quarantine

Do not pretend Dataflare's single `train` split is a scientifically valid train/test design.

## Manual gold validation gate

Design and materialize a stratified manual-review set before claiming classifier or citation-parser accuracy.

Target approximately 200 records, with coverage across judicial, administrative, legislative, constitutional/international, forms/commentary/academic, and ambiguous/unknown cases.

Gold fields should support at least:

- `gold_document_type`
- `gold_identity`
- `gold_structure_presence`
- `gold_citation`
- reviewer/adjudication status

Until labeled, metrics are coverage/distribution only.

## Resource measurement

A statement such as `completed in under one second` is not a benchmark unless accompanied by environment and measurement metadata.

For corpus-wide Stage 1 processing, record when practical:

- wall time
- peak RSS/RAM
- Python version
- OS
- CPU information
- dataset SHA
- software commit

Keep Stage 1 stdlib/lightweight where possible. Do not load LLMs or embedding models for metadata classification.

## Clean repository mission

After reconciling local work, inspect the full tree and make it match `docs/REPOSITORY_STRUCTURE.md` without destroying useful history.

Rules:

1. Keep the root small.
2. Remove superseded architecture drafts/promotion artifacts from the working tree; Git history is sufficient archival storage unless they contain active research value.
3. Consolidate stale hardware/portability README variants into `docs/runbooks/`.
4. Keep research/corpus investigations under `docs/research/` if they remain active.
5. Merge duplicate instructions into canonical docs instead of keeping multiple partially conflicting files.
6. Do not delete code merely because it is old if it is still used by a supported runtime path.
7. Root `app.py` is known Stage 3 migration debt: do not expand it, and do not delete it during Stage 1 unless all supported entrypoints have proven parity and the authorized stage explicitly permits it.
8. Do not create generic `utils.py` dumping grounds or duplicate parsers.
9. Update references after every move/delete.
10. Run a repository-wide search for stale filenames, obsolete commands, old paths, and superseded baseline claims.

## Clean-code standard

Use Python 3.12, type hints on public interfaces, small cohesive modules, pathlib, deterministic logic, explicit error/result types, structured logging, and focused tests.

Avoid god classes, mega-functions, hidden global state, broad exception swallowing, magic regex without tests, duplicate business logic, unnecessary dependencies, and speculative abstractions.

Prefer composition over inheritance and explicit domain contracts over dictionaries with undocumented keys.

## Future platform readiness

Do not build mobile clients now, but preserve stable client-independent backend contracts for future web/iOS/Android/enterprise clients.

Future product boundaries must support:

- evidence/source inspection
- legal version/as-of date
- warnings/abstention
- privacy and data minimization
- external-provider data boundaries
- account deletion/retention policies when product accounts exist
- auditability

Do not claim Apple App Store or Google Play compliance from architecture alone; current store policies must be reviewed at release time.

## Testing truthfulness

Never call a run `full suite` if tests were excluded.

Report exactly:

- executed tests and pass count
- skipped/excluded tests and why
- pre-existing failures separately
- lint result
- type-check result
- integration/regression result

If FAISS or another optional dependency prevents a test from running, state that explicitly and preserve a CI/environment plan to exercise it.

## Required engineering sequence

1. Reconcile local/unpushed Stage 1 changes with remote branch.
2. Produce a concise gap/diff report.
3. Complete canonical contracts without duplicate implementations.
4. Reproduce real Dataflare metrics.
5. Materialize manifest/report/split artifacts.
6. Build the manual-gold review manifest.
7. Run focused unit tests.
8. Run integration and real-data regression tests.
9. Run lint/type checks.
10. Run all repository tests that the environment supports and explicitly list exclusions.
11. Measure Stage 1 resource behavior.
12. Perform adversarial architecture/data/security review.
13. Fix only justified findings.
14. Re-run affected gates.
15. Update docs and decision records.
16. Clean the repository tree and stale references.
17. Commit and push to `feat/enterprise-foundation`.
18. Return commit SHA(s), exact changed/deleted/moved files, test commands/results, artifact paths, unresolved risks, and a strict `STAGE 1 READY` or `NOT READY` verdict.

## Stop conditions

Stop and surface the problem instead of guessing when:

- legal identity is ambiguous
- source authority/provenance is uncertain
- deduplication could destroy meaningful provenance/version information
- parser boundaries may be fabricated
- held-out evaluation could leak
- a request conflicts with `ARCHITECTURE_CONTRACT.md`
- local and remote branches diverge in a way that risks data loss

## Final product principle

We are building legal evidence infrastructure capable of answering not only `what text is similar?` but eventually:

- what is the governing legal resource?
- where did it come from?
- what version applied at the relevant time?
- what court interpreted or applied it?
- what evidence supports each material claim?
- what evidence is missing or conflicting?
- when should the engine abstain?

Do not optimize for quantity of code. Optimize for trustworthy legal intelligence and a codebase that a senior engineering team can maintain for years.
