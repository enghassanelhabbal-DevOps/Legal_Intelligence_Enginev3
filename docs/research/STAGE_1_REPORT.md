# Stage 1 Report — Dataset Intake + Leakage-Safe Evaluation Foundation

Branch: `feat/enterprise-foundation`. Scope: `LEGAL_INTELLIGENCE_ENGINE — STAGE 1 EXECUTION MASTER PROMPT`.

## 1. What was built (implemented, tested, and run against the real corpus)

| File | Purpose |
|---|---|
| `src/legal_ai/evaluation/dataset_manifest.py` | `DatasetManifest` contract; `TaskRole`/`LicenseStatus`/`QualityStatus`/`LeakageStatus` enums; explicit `unknown`/`not_applicable` sentinels; manifest hashing; JSON round-trip; training-role license gate. |
| `src/legal_ai/evaluation/dataset_profiler.py` | Bounded, stdlib-only, single-pass profiler: record counts, missing fields, exact-duplicate and normalized-text near-duplicate counts, text-length/language/jurisdiction/law distributions, citation completeness, content hash (reuses `ingestion/validation.hash_document`). |
| `src/legal_ai/evaluation/leakage.py` | Group-key derivation (`law_id`→`document_id`→`source_id`→`case_id`→`question_group`, else self-group), deterministic seeded group-level split assignment, cross-dataset exact-match overlap detection with explicit candidate-schema field mapping, `enforce_no_overlap` for CI. |
| `src/legal_ai/evaluation/dataset_intake.py` | Single canonical CLI (`profile`, `validate`, `leakage`, `split`, `report`), JSON-only output, typed exit codes (0 pass / 1 fail / 2 usage-error). Also installed as `legal-ai-dataset` console script. |
| `src/legal_ai/core/exceptions.py` | Added `DatasetManifestError`, `DatasetLeakageError`, `DatasetSplitError` (3, not 7 — reused `IngestionError`/`EvaluationError` where the failure mode was already covered). |
| `tests/test_dataset_manifest.py`, `test_dataset_profiler.py`, `test_leakage.py`, `test_dataset_intake_cli.py` | 51 new tests: unit, synthetic-fixture integration (duplicates, near-duplicates, amended versions, multi-chunk law, mixed jurisdiction, mixed Arabic/English, missing metadata), CLI/exit-code integration, and one regression test against the real 952-article corpus. |
| `dvc.yaml` | New `dataset_profile` stage producing `artifacts/reports/dataset_profile.json`, following the existing stage pattern. |
| `docs/ENGINEERING_DECISION_REGISTER.md` | DR-017 (grouping-key default + overlap-check schema-explicitness). |

**Test results:** 65/65 passing (`pytest tests/ --ignore=tests/test_retrieval.py`; the excluded file fails on `import faiss` in this sandbox, confirmed pre-existing via `git stash` before any Stage 1 change — not a regression). Ruff and mypy clean on all new/modified files.

## 2. Real findings surfaced by this work (not invented, not hidden)

**(a) Data quality defect in the production corpus.** `profile_dataset` against `legal_documents.json` reports `missing_required_fields: {"article_id": 468}` and `citation_completeness: 0.508`. Verified independently: **all 468 records of قانون العقوبات (Penal Code) have an empty `article_id`**, while all 484 records of قانون الإجراءات الجنائية (Criminal Procedures Code) have it populated. This means citations built from Penal Code evidence currently carry no article number — a real, previously-undetected defect affecting half the corpus. This was not something Stage 1 was asked to fix; it is reported here as required ("do not silently downgrade requirements" — a defect found and not reported would be exactly that).

**(b) A vacuous-pass bug in my own first leakage-check implementation, caught before shipping.** My first version of `check_overlap` compared `raw_text`/`document_id` fields against `data/evaluation/eval_queries.json`, whose records use `query`/`relevant_document_ids` instead. It silently reported `is_clean: true` — a leakage check that checked nothing looked identical to one that passed. Fixed by adding `candidate_text_field`/`candidate_id_field` mapping and an `is_meaningful` flag that `enforce_no_overlap` treats as a failure by default. Regression-tested (`test_mismatched_schema_is_flagged_not_silently_clean`, `test_leakage_command_vacuous_schema_mismatch_exits_nonzero`) so this class of bug cannot silently reappear. Documented as DR-017.

**(c) Grouping by `law_id` degenerates on the current corpus.** Only 2 distinct `law_id` values exist, so group-level splitting of the *raw corpus* puts everything in one bucket (952/0/0). This is correct leakage-safety behavior, not a bug — but it means `split` is only meaningful when applied to *evaluation query sets* (many queries per law/article) rather than to the source legal text itself. Documented in DR-017 so Stage 2+ doesn't rediscover this by trial and error.

## 3. Deferred scope (explicit, not silent)

Per Stage 1's own instruction ("do not over-engineer fields that are not yet justified"), the following DATA_GOVERNANCE.md-listed fields/features exist in the manifest contract only as placeholders or are not yet implemented, and are **not** claimed as done:

- `legal_systems`, `authority_types` beyond a flat unknown-by-default list — no authority-type taxonomy exists yet to populate them meaningfully.
- `date_coverage` — the current corpus has no date fields at all (`version_id` is `null` for all 952 records), so this is correctly `unknown`, not fabricated.
- Semantic/embedding-based near-duplicate detection — the current near-duplicate check is exact-string-on-normalized-text, which is cheap and bounded but will miss paraphrase-level near-duplicates. Documented as a limitation, not silently claimed as "near-duplicate detection: done."
- The full L1–L10 evaluation-level evaluator and `EvaluationCase` contract (§15/§16 of the master prompt) — the data contracts (`TaskRole`, manifest fields) do not block adding these later, but the evaluator itself is not built in Stage 1, per the master prompt's own "does not need the full evaluator for every level" allowance.
- DVC pipeline reproducibility was verified by running the wired command directly; `dvc repro` itself was not executed in this sandbox (no DVC remote/cache configured here) — the stage definition is added and the underlying command is confirmed working.
- Second-dataset validation is architecturally supported (the CLI and profiler take any list-of-dict or `{"queries": [...]}` shaped file, not a hardcoded schema) but has only been exercised against `legal_documents.json` and `eval_queries.json` — no second real dataset exists yet to test against, per the master prompt's own framing ("assume the project owner will provide a second dataset").

## 4. Claude adversarial self-review (Step 7)

- **Architecture:** Follows the required layering — no Streamlit/HTTP/LLM-provider imports in `evaluation/`; reuses `ingestion/validation.hash_document` rather than reimplementing hashing (avoids a 3rd hashing implementation alongside `ingestion` and the old regression harness).
- **Correctness:** All 51 new tests pass; the one defect found during self-testing (vacuous leakage check) was fixed and regression-tested, not just noted.
- **Data leakage:** Group-level (not record-level) split assignment is deterministic and seeded; `enforce_no_overlap` fails loudly by default, including on vacuous checks.
- **Legal data integrity:** No `raw_text` is mutated anywhere in this module; profiling and hashing are read-only over the input.
- **Resource use:** Stdlib-only, single-pass, O(n); no model loads; profiling the full 952-record corpus completes in well under a second.
- **Security:** No path traversal, no archive extraction, no shell execution; `_load_records` only reads a single JSON file at a caller-supplied path (same trust boundary as existing scripts).
- **Determinism:** Split assignment is a pure function of `(records, seed, group_fields)` — verified by `test_split_is_deterministic_for_same_seed`.
- **Future extensibility:** Adding a second dataset requires no new pipeline code (CLI accepts any compatible record shape); adding a new task role requires one enum entry, not new validation logic.
- **Simplicity:** No plugin framework was built (explicitly disallowed by the master prompt); the smallest abstraction (a field-preference list plus a shape-detection fallback) was used instead of a schema-registry system.

**Honest limitation this review does NOT resolve:** the near-duplicate detector's blindness to paraphrase-level duplication remains a real gap for a legal corpus, where amended-article paraphrasing is plausible. This is out of Stage 1's stdlib-only, no-model-loading budget by design, and is recorded as future work rather than silently left unstated.

## 5. Stage 1 exit criteria (§37)

```text
[x] Existing 952-article corpus can be profiled
[x] A second dataset can be profiled without custom pipeline code (architecturally — CLI is schema-flexible; not yet exercised on a real second dataset, see §3)
[x] Dataset provenance is explicit (recorded as "unknown", not guessed, when absent)
[x] License state is explicit (LicenseStatus.UNKNOWN blocks training task_roles)
[x] Schema is validated (DatasetManifestError on bad task_roles; profiler reports missing/malformed fields)
[x] Roles are explicit (TaskRole enum, validated in __post_init__)
[x] Leakage checks are reproducible (seeded, deterministic)
[x] Held-out evaluation split is protected (enforce_no_overlap raises DatasetLeakageError, fails loudly on vacuous checks too)
[x] Split generation is deterministic (seed + strategy recorded and tested)
[x] Machine-readable reports exist (JSON-only CLI output)
[x] CLI works in CI (typed exit codes 0/1/2, tested)
[x] Unit tests pass (51/51 new, 65/65 total excluding pre-existing faiss gap)
[x] Integration tests pass (CLI + synthetic fixtures)
[x] No unsafe path handling exists (single-file JSON read only)
[x] No new duplicate business logic exists (reuses hash_document; no second hashing/validation implementation)
[x] No retrieval quality claims are invented (this work does not touch retrieval)
[x] No legal-understanding claims are invented
[x] No fine-tuning is introduced
[x] Resource behavior is measured (stdlib-only, sub-second on full corpus, no model loads)
[x] Claude review is completed (§4 above)
[ ] Findings are explicitly resolved or accepted — pending project-owner sign-off (§2a article_id defect is reported, not fixed, since fixing corpus data is outside Stage 1 scope)
[x] Documentation is synchronized (DR-017 added; this report added)
```

## 6. Step 8 — Human/project-owner gate: RESOLVED

Both pending decisions were resolved with concrete paths, not passive choices (see DR-018, DR-019):

1. **`article_id` gap** — accepted as debt, with a concrete recovery path attached: cross-reference against Dataflare's Penal Code text once ingested (DR-018). Automated recovery from the *existing* corpus alone was attempted and confirmed impossible — the article number is not present in any field, not just missing from `article_id` (verified exhaustively across all 9 fields).
2. **Deferred fields** — confirmed deferred, tied to a concrete trigger (first real Dataflare ingestion) rather than an open-ended "later" (DR-019).

## 7. Dataflare pre-ingestion work (this session)

`docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md` was reviewed and used to drive genuine pre-ingestion engineering, not just planning text:

| File | Purpose |
|---|---|
| `src/legal_ai/ingestion/article_segmentation.py` | Deterministic Arabic article-boundary parser (`المادة N`, `مادة N`, `N مكرر`, ordinal-word forms). Foundation for H2 (article-aware chunking) and the Dataflare processing plan's "Article/section structure extraction" step. |
| `src/legal_ai/evaluation/dataset_adapters.py` | Schema-adapter registry (`identity`, `dataflare_egypt_legal_corpus`) mapping Dataflare's public schema (`law_name`/`categories`/`text`/`tokens`) into the canonical shape the profiler/leakage tools already understand — the Stage 1 "second dataset requires no bespoke pipeline code" exit criterion, exercised now instead of only claimed. |
| `docs/research/RESEARCH_HYPOTHESES.md` | H1–H5 formalized as falsifiable claims: precise statement, falsification condition, experiment cross-reference (Dataflare assessment's Experiments A–E, plus a new Experiment F for H2), primary metric, minimum evidence bar, and an explicit dependency graph (H2 → H1 → H4 → H5 gate; H3 independent). |
| `tests/test_article_segmentation.py`, `tests/test_dataset_adapters.py` | 18 new tests, including an end-to-end test proving a Dataflare-schema-shaped dataset is profilable via `apply_adapter` + `profile_dataset` with zero new pipeline code. |

**Test results:** 83/83 passing (up from 65). Ruff and mypy clean on all new files.

### Honest limitation — I could not fetch the actual Dataflare data

This sandbox's network egress is restricted to package registries and GitHub (`api.anthropic.com`, `pypi.org`, `github.com`, etc.) — `huggingface.co` is not in the allowed domain list. I attempted `datasets.load_dataset('dataflare/egypt-legal-corpus')` directly to confirm rather than assume, and it failed with a connection error, not a data error. This means:

- Everything above (segmenter, adapter, hypothesis registry) was built and tested against **synthetic fixtures matching the documented public schema**, not the real 25M-token corpus.
- The article segmenter's real precision/recall, the adapter's actual field coverage, and every H1–H5 experiment are **unvalidated against real data** until the corpus is actually ingested.
- To unblock real ingestion, one of two things needs to happen: (a) the network allowlist for this environment gets `huggingface.co`/`datasets-server.huggingface.co` added, or (b) the dataset (or a representative sample/parquet export) is uploaded directly as a chat attachment, which bypasses network restrictions entirely since it lands on local disk.

This is stated plainly rather than silently treating the synthetic-fixture tests as if they validated real-world behavior — they validate the *code*, not the *data assumptions*.

