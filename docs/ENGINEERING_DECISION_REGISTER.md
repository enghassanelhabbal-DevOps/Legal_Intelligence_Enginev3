# Engineering Decision Register

This register records durable architectural decisions. New decisions should be added rather than silently rewriting history.

## DR-001 — v3 is the canonical foundation

Status: accepted.

Decision: Continue from `Legal_Intelligence_Enginev3`; do not rewrite from zero.

Reason: v3 already contains the strongest known modular retrieval, API lifecycle, LLM adapter, evaluation, DVC, Docker, and CI foundation.

Consequence: legacy duplicate paths become migration debt, not justification for a wholesale rewrite.

## DR-002 — Evidence-first architecture

Status: accepted.

Decision: Retrieval and evidence precede generation. The LLM is not the source of legal truth.

Consequence: every answer path must expose evidence/provenance and cannot bypass evidence validation.

## DR-003 — Knowledge updates do not normally require model retraining

Status: accepted.

Decision: Current legal updates enter through versioned ingestion, indexing, and knowledge releases.

Consequence: the base LLM can remain replaceable and knowledge remains independently auditable.

## DR-004 — Historical 0.835 retrieval score is not a trusted protected baseline

Status: accepted.

Decision: Treat the historical 0.835 hybrid figure as unverified until a reproducible harness and artifact lineage are recovered.

Consequence: current CI smoke metrics remain regression guards only; a full production-pipeline benchmark must be established.

## DR-005 — Retrieval and legal understanding are separate measurements

Status: accepted.

Decision: Never infer legal understanding from retrieval Recall/MRR.

Consequence: expert-labeled reasoning, entailment, temporal, jurisdiction, and abstention benchmarks are required.

## DR-006 — Resource efficiency is a product requirement

Status: accepted.

Decision: Support CPU-only, constrained GPU, normal GPU, and remote inference through one domain contract.

Consequence: bounded workers, batching, model residency, and graceful degradation are first-class concerns.

## DR-007 — Failure learning is controlled, not self-modifying

Status: accepted.

Decision: Failures can create telemetry and regression cases, but runtime cannot silently modify code, prompts, thresholds, knowledge, or model weights.

Consequence: improvements enter through reviewed releases.

## DR-008 — Claude is an implementation and adversarial-review partner

Status: accepted.

Decision: Substantial stages use Claude for code implementation/review, while the review step is separated from any authorized production change.

Consequence: review findings must be resolved and re-tested before merge.

## DR-009 — Egypt first, jurisdiction packs later

Status: accepted.

Decision: Initial product wedge targets Egyptian legal research. Additional jurisdictions are explicit versioned packs.

Consequence: data, evaluation, authority semantics, and temporal coverage remain jurisdiction-scoped.

## DR-010 — No premature distributed architecture

Status: accepted.

Decision: Scale single-node correctness first, then efficiency, reliability, stateless horizontal API, and only then distributed components if measured demand requires them.

Consequence: Kubernetes/microservices/distributed vector search are not first-stage requirements.

## DR-011 — Human/legal expert validation remains necessary

Status: accepted.

Decision: Legal-domain semantics such as authority, ambiguity, amendments, conflicts, and expert gold answers require domain review where model-based validation is insufficient.

Consequence: the benchmark process must support expert annotation and disagreement tracking.

## DR-012 — No claim without reproducible evidence

Status: accepted.

Decision: Accuracy, latency, memory, throughput, cost, and reliability claims require reproducible reports.

Consequence: benchmark artifacts and experiment manifests become part of release evidence.

## DR-013 — Canonicalize Gemini generation backend

Status: accepted.

Decision: Gemini is a named remote LLM provider in the current production path and must be represented by a canonical `GeminiBackend` under `src/legal_ai/generation/backends/`, conforming to the shared generation adapter contract.

Current state: provider-specific Gemini behavior currently exists in root `app.py`, including model-variant fallback and bounded retry behavior. This is treated as technical debt and a second generation implementation, analogous to the previously identified retrieval duplication.

Migration rule:

```text
inventory current Gemini behavior
→ define adapter parity contract
→ implement GeminiBackend
→ add parity/failure/resource tests
→ route QueryService/GenerationManager through canonical backend
→ verify supported behavior and metrics
→ remove vendored Gemini implementation from app.py
→ repository-wide search confirms one active Gemini implementation
```

Provider/data-boundary policy: Gemini is an external trust boundary. The system must make the selected provider explicit and must not send data classified as disallowed for that provider. Provider credentials and sensitive payloads must not appear in logs, fixtures, or committed files.

Consequence: Gemini provider changes belong to the generation layer and its configuration; retrieval, evidence, API, and UI must remain provider-agnostic.

## DR-014 — Root app.py is not a permanent business-logic boundary

Status: accepted.

Decision: Deployment convenience, including single-process Streamlit hosting constraints, does not justify active duplicate retrieval or generation business logic in root `app.py`.

Decision rule: Any new capability first added to `app.py` for deployment convenience is presumptively a duplication violation unless it is presentation/transport-only or has an explicit, versioned migration path into the canonical `src/legal_ai` layer.

Consequence: Stage 3 must remove retrieval and generation duplication and preserve only thin entrypoint behavior where necessary.

## DR-015 — Stage 4 owns the full production retrieval benchmark

Status: accepted.

Decision: The reproducible benchmark for the exact dense + lexical + reranker production retrieval path is a Stage 4 deliverable and the gate for later retrieval optimization claims.

Consequence: no full-stack retrieval optimization claim may rely only on the current BM25 smoke gate or the unverified historical 0.835 figure.

## DR-016 — Security controls are staged by risk

Status: accepted.

Decision: Security controls are implemented according to execution risk and product maturity rather than as one undifferentiated enterprise backlog.

Consequence: baseline secrets/data/file/prompt boundaries begin in early stages; tenant isolation, data residency, and enterprise governance are introduced when the commercial platform requires them.

## DR-017 — Default leakage-grouping key is law_id, exact-match overlap checks are schema-explicit

Status: accepted.

Decision: The Stage 1 dataset intake system (`src/legal_ai/evaluation/leakage.py`) groups records for split-safety using the first present field from `[law_id, document_id, source_id, case_id, question_group]`, defaulting to `law_id` for the current corpus since every record carries it. This is a leakage-safety grouping key, not a split-quality guarantee: profiling the real 952-article corpus showed only 2 distinct `law_id` values, so grouping the raw corpus itself by `law_id` produces a degenerate (all-or-nothing) split. Splitting must be applied to *evaluation query sets* derived from the corpus (grouped by which law/article they reference), not to the raw corpus text itself.

Cross-dataset overlap checks (`check_overlap`/`enforce_no_overlap`) require the caller to state which field holds text/id in the *candidate* dataset when it differs from the protected dataset's schema (e.g. an eval-query set's `query`/`relevant_document_ids` vs a corpus's `raw_text`/`document_id`). A check across mismatched field names that finds nothing must be reported as `is_meaningful=False`, not as a passing "clean" result — this was a real defect caught during Stage 1 implementation (an unmapped leakage check against `data/evaluation/eval_queries.json` silently reported 0 overlaps because it was comparing fields that don't exist in that file's schema) and is now a CI-failing condition by default in `enforce_no_overlap`.

Consequence: Stage 2+ work adding a second dataset must supply an explicit grouping-field list and candidate-field mapping rather than relying on defaults tuned for the current single-jurisdiction, two-law corpus; and any future overlap/leakage check must set or verify `is_meaningful` before trusting a "clean" result.

## DR-018 — Penal Code article_id gap: accepted as debt with a concrete recovery path, not a passive deferral

Status: accepted.

Decision: All 468 `قانون العقوبات` (Penal Code) records in `legal_documents.json` have an empty `article_id`, while all 484 `قانون الإجراءات الجنائية` (Criminal Procedures) records have it populated. Automated recovery from the existing corpus was attempted and confirmed impossible: the article number is not recoverable from `raw_text`, `normalized_text`, `embedding_text`, `source`, or `version_id` — none of these fields carry it independently (`embedding_text` was itself generated from the empty `article_id`, so it is not an independent source).

Rather than a binary accept-or-fix choice, the resolution is: accept the current gap as known debt (no re-scrape of the original legal source is in scope now), **and** create a concrete, already-planned recovery path: `docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md`'s Experiment E (overlap analysis against the existing 952 corpus) must include cross-referencing Penal Code text against Dataflare's Penal Code records once ingested, since Dataflare's raw text is expected to retain in-line "المادة N" markers (`src/legal_ai/ingestion/article_segmentation.py`) that this corpus's ingestion pipeline apparently discarded for this one law. If that cross-reference succeeds, article_id can be backfilled with `provenance: "cross_reference_derived"`, never silently presented as original.

Consequence: Experiment E's required outputs now explicitly include an article_id backfill assessment for the Penal Code subset, not just a general overlap report.

## DR-019 — Deferred manifest fields confirmed acceptable, tied to Dataflare intake rather than left open-ended

Status: accepted.

Decision: The fields deferred in Stage 1 (`legal_systems`/`authority_types` taxonomy, `date_coverage`, semantic near-duplicate detection, full L1–L10 evaluator) remain deferred, but not indefinitely and not unmotivated: Dataflare's `categories` field gives the first real signal to populate `authority_types`/`legal_systems` meaningfully once ingested, and the hierarchical structure work required for H1/H2 (`docs/research/RESEARCH_HYPOTHESES.md`) will produce article-level granularity that a semantic near-duplicate detector can be built against later without redesigning the profiler.

Consequence: these fields are re-evaluated at first real Dataflare ingestion, not at an unscheduled future date; `DatasetManifest`'s existing `unknown` sentinel already accommodates them without schema changes.

## DR-020 — Suspected extraction-noise in Dataflare text is flagged, not silently stripped

Status: accepted.

Decision: A 10-row real sample fetched from the Dataflare public viewer (see `docs/research/DATASET_ASSESSMENT_DATAFLARE_EGYPT_LEGAL_CORPUS.md`, "Real sample findings") showed multiple unrelated records opening with a short meaningless token + small number (e.g. `"دودو 10 قانون..."`) before real legal content, consistent with an OCR/extraction artifact. A detector (`src/legal_ai/ingestion/text_quality_diagnostics.py`) was built and tested against the exact observed strings, but per the "do not guess, do not silently fix data" governance rule, it only flags suspected noise for manifest/report visibility — it does not strip or alter text. No cleaning rule is adopted yet: a 10-row sample (~0.4% of the corpus) is not sufficient to establish the pattern's true prevalence, false-positive rate, or correct removal boundary.

Consequence: `scan_corpus_for_noise_prefix` must be run against the full corpus at first real ingestion, and its prevalence/false-positive findings must be reviewed before any text-cleaning transformation is added to the ingestion pipeline. Until then, `article_segmentation.py`'s existing design (unmatched text before the first `المادة` marker is captured separately, never treated as article content) already provides a safe fallback — noise prefixes do not corrupt article boundary detection even before a dedicated cleaning rule exists.

## DR-021 — Dataflare corpus is 86.7% case law by record count; taxonomy and grouping strategy revised accordingly

Status: accepted.

Decision: Full-corpus analysis of the real parquet file (2,434 records, confirmed via direct download) found 2,110 records (86.7%) are Court of Cassation (نقض) case-ruling excerpts, not statute text, identified by the citation pattern `"الطعن رقم N لسنة Y مكتب فنى O"`. `law_name` is overloaded: for statutes it is the law's title; for case rulings it is a legal-doctrine/topic label shared across many unrelated rulings (e.g. `"المنع من سماع الدعوى"` appears against 5 distinct, unrelated cases). Using `law_name` as the leakage-safety grouping key (DR-017's default) for case-ruling records would therefore incorrectly group unrelated cases sharing a topic label into one leakage-safety cluster.

Consequence: the case-citation key (`case_citation_extraction.citation_key()` — appeal number + year + technical office) must be used as the grouping key for case-ruling records during Dataflare ingestion; `law_name`/`law_id` remains correct only for the statute-like 13.3% subset. `src/legal_ai/evaluation/leakage.py`'s `group_key_for` field-preference list should add citation-derived grouping for this dataset at ingestion time (tracked for the actual ingestion implementation, not done in this exploratory pass). This is a positive product finding, not a downgrade: case-ruling excerpts with clean citation extraction (94.8% coverage, measured) are exactly the citable evidence units the groundedness goal (H4) needs.

## DR-022 — Article-boundary segmenter rebuilt after 99.7% real-data miss rate; root cause was a synthetic-fixture assumption

Status: accepted.

Decision: `article_segmentation.py` was originally built and unit-tested only against synthetic fixtures with newline-separated articles (`"المادة 1 - ...\n\nالمادة 2 - ..."`). Run against the real corpus, it found zero markers in 323 of 324 statute-like records (99.7% miss). Root cause: real Dataflare statute text is a single continuous flattened paragraph with no internal newlines at all, and the segmenter's marker pattern required a line-start anchor. Fixed by matching the marker anywhere in text, with an exclusion for referential mentions (`"طبقا للمادة 5"`) so a reference to an article is not double-counted as a second boundary. Post-fix miss rate: 17.2% (56 of 326), and inspection confirmed these are not remaining bugs — they are genuinely structure-less content (lawsuit petition templates, legal notice forms, explanatory prose) that correctly has no article markers.

Consequence: any future ingestion module built and tested only against synthetic/hand-written fixtures must be validated against a real sample of the target corpus before being treated as ready — this specific failure mode (works on synthetic fixtures, fails almost completely on the real distribution) is now a named risk pattern for this project, not a one-off bug.

## DR-023 — DR-018's Dataflare cross-reference recovery path for the Penal Code article_id gap is revised, not retracted

Status: accepted (supersedes the optimistic framing in DR-018, not the underlying decision to accept the gap as debt).

Decision: Full-corpus analysis found Dataflare's only Penal-Code-titled record is `"نموذج كــود قانون العقوبات"` ("Model Code draft of the Penal Code") — not confirmed identical in content or legal authority to the production Penal Code already in `legal_documents.json`, and zero exact-text overlap was found between the two datasets (expected, since Dataflare stores each law as one giant record vs. one-record-per-article in the existing corpus — exact matching cannot find overlap across that granularity difference regardless of content similarity). DR-018's proposed recovery path (cross-reference Dataflare text to backfill `article_id`) therefore requires, before it can be attempted: (a) article-level segmentation of the Dataflare "Model Code" entry via `article_segmentation.py`, (b) fuzzy/substring matching at the segment level rather than exact full-text matching, and (c) explicit verification that the "Model Code" text is legally equivalent to the production law, not just similarly named, before any backfilled `article_id` could be trusted enough to use.

Consequence: the Penal Code `article_id` gap remains accepted debt with a *harder, multi-step* recovery path than DR-018 originally described, not a straightforward one. This must be reflected in Stage 2+ planning effort estimates.

## DR-024 — NFC normalization is required before any hardcoded-Arabic-marker matching; three real bugs found and fixed

Status: accepted.

Decision: independently re-verified the correction that NFC normalization *does* resolve decomposed Arabic hamza combining marks (previously misreported as not working — the earlier test compared a hand-typed marker against another hand-typed comparison string, both potentially sharing the same typing artifact, rather than against real data). Root-caused precisely: real Dataflare `categories` text uses decomposed sequences (e.g. base+YEH+COMBINING-HAMZA-ABOVE, U+0654) where a hand-typed precomposed marker (e.g. `"نقض جنائي"`) would silently fail to match — confirmed to be the exact cause of a real bug in `document_type.py`'s classifier, which returned zero `JUDICIAL_CASSATION_CRIMINAL` results against the full real corpus despite 415 records genuinely being criminal cassation rulings.

Fixed by adding `nfc_normalize()` to `ingestion/normalization.py` (NFC-only, deliberately less aggressive than the existing `normalize_arabic()` — no lowercasing/alef-merging/diacritic-stripping, so it stays safe for offset-sensitive operations) and applying it to both input text and hardcoded marker constants in `document_type.py`, `article_segmentation.py`, `case_citation_extraction.py`, and `text_quality_diagnostics.py` — all four modules had at least one marker containing a hamza-bearing letter (أ إ ؤ ئ ء) and were therefore exposed to the same silent-failure class.

Consequence: any future module that matches hardcoded Arabic strings against real corpus text must apply `nfc_normalize()` first — this is now a named, tested risk pattern (regression tests built the decomposed sequences programmatically, not by hand-typing, specifically to avoid re-introducing the same class of bug via the test itself).

## DR-025 — Document-type classifier: category-tag substring collision and hierarchical-tag ordering bugs found and fixed during real-corpus validation

Status: accepted.

Decision: building `domain/document_type.py`'s rule-based classifier against the real corpus surfaced two real bugs before either shipped:

1. **Substring collision**: an early administrative-court marker (`"المحكمة الادارية"`) is a literal substring of the combined category tag `"النقض و المحكمة الادارية"` (cassation-and-administrative, a genuinely mixed bucket applied to 2,051 records), causing every combined-tag record to be wrongly classified as pure `JUDICIAL_ADMINISTRATIVE`. Fixed by narrowing the marker to Supreme-Administrative-specific tags only (`"اداريا عليا"`, `"الادارية العليا"`) that do not collide with the combined tag.
2. **Ordering**: categories in this corpus are hierarchical — a specific sub-tag (`"نقض مدني"`, `"نقض جنائي"`, `"اداريا عليا"`) normally co-occurs *with* the broad combined parent tag on the same record (confirmed: 1293+415+343 = 2051, exactly the combined-tag count). Checking the combined tag first meant the specific sub-type check was never reached. Fixed by checking specific sub-type markers before falling back to the combined/ambiguous case.

Post-fix, measured against the full real corpus: 1293 civil cassation, 415 criminal cassation, 343 administrative, 179 statute, 105 constitutional, 59 judicial-other (genuinely ambiguous), 17 unknown (0.7%), matching the independently-measured category tag counts exactly.

Consequence: `docs/research/RESEARCH_HYPOTHESES.md` and future classifier work should treat "validate against real data before trusting a rule-based marker list" as a standing requirement, not a one-off step — this is the second time in this project a synthetic/assumption-based first pass silently failed at a high rate on real data (the first was DR-022's article segmenter).

## DR-026 — Duplicate clustering: record_id must be excluded from metadata-variance comparison

Status: accepted.

Decision: `domain/duplicate_clustering.py`'s first implementation compared full per-record metadata dicts (including `record_id`) to decide whether a duplicate-text cluster was an "exact duplicate" or a "metadata variant" — since `record_id` always differs between distinct members, every multi-member cluster was wrongly flagged as a metadata variant. Fixed by comparing only the caller-specified `metadata_fields` values. Measured against the real corpus: of 347 duplicate-text clusters (696 records), only 7 are genuine metadata variants (e.g. `law_name` values `"New Microsoft Word Document"` and `"law4_arb"` appearing as variants of `"قانون البيئة"` — confirms the dataset card's own claim that `law_name` derives from source filenames); the remaining 340 are true exact duplicates safe to canonicalize.

Consequence: the 7 genuine metadata-variant clusters are flagged for manual review per the master prompt's "prepare outputs for manual legal review where appropriate" requirement, not auto-resolved.

## DR-027 — Citation-based grouping wired into leakage-safety splitting for judicial records (DR-021 follow-through)

Status: accepted.

Decision: `evaluation/leakage.py`'s `group_key_for` now checks a `citation_key` field first (via the new `enrich_with_citation_key()` helper, which runs `case_citation_extraction.extract_case_citation()` per record), falling through to `law_id` for legislative records where citation extraction is not applicable (returns `None`, not a fabricated value). Verified against the real corpus: the 5 records sharing the topic label `"المنع من سماع الدعوى"` (used in DR-021 as the motivating example) now resolve to 2 distinct group keys instead of being forced into a single group by the shared topic label alone.

## DR-028 — Stage 2 runtime foundation: CUDA discovery moved to a spawned subprocess to remove a confirmed deadlock risk

Status: accepted.

Decision: `src/legal_ai/runtime/hardware.py`'s `probe_cuda()` never calls `torch.cuda.is_available()`/`torch.cuda.get_device_properties()` in-process. An in-process probe carries a confirmed deadlock risk once a CUDA context has already been initialized in a process that is later forked — CUDA is not fork-safe, and a forked child can hang inside the driver indefinitely rather than raising a catchable exception. This project has at least three fork-affected paths that could trigger it: pytest-xdist worker forking, Streamlit's re-run/thread execution model, and any future use of `multiprocessing` with the default "fork" start method on Linux/WSL2. Fixed by running the CUDA probe as a small, self-contained script in a freshly *spawned* subprocess (`subprocess.run([sys.executable, "-c", ...])`), which never inherits the parent's CUDA context, combined with a hard timeout (default 15s) so a misbehaving driver degrades to `probe_status="timeout"` instead of hanging the caller. Every other hardware signal in `discover_hardware()` (CPU count, RAM, storage) also follows the same "degrade to an explicit unavailable status, never raise" rule from RESOURCE_RELIABILITY_SPEC.md §3, including a `psutil`-optional fallback to `/proc/meminfo` on Linux for RAM discovery when `psutil` is not installed.

Consequence: `psutil` is used opportunistically (`try`/`except ImportError`) for CPU-physical-core-count and RAM discovery but is not yet declared as a hard dependency in `pyproject.toml`. Recommended follow-up: add `psutil` to the core `dependencies` list so RAM/CPU discovery gets full fidelity on every supported platform (Windows in particular has no `/proc/meminfo` fallback) rather than relying on best-effort degradation. `ExecutionProfile` resolution (`profiles.py`) and per-profile `ResourceBudget`s (`budgets.py`) are pure functions over the resulting `HardwareSnapshot` and therefore fully unit-testable without a GPU, torch, or psutil present — verified by `tests/test_hardware.py`, `tests/test_execution_profiles.py`, and `tests/test_resource_budgets.py` running clean in a torch-less CI sandbox.

## DR-029 — `psutil` promoted to a hard dependency; CPU sizing made container/affinity-aware instead of `os.cpu_count()`-only

Status: accepted.

Decision: `psutil>=6.0,<8` was added to `pyproject.toml`'s core `dependencies` (resolving DR-028's flagged follow-up), giving deterministic physical-core-count and total-RAM discovery on every supported platform instead of the previous best-effort `/proc/meminfo` fallback (which only covered Linux). Separately, a new `src/legal_ai/runtime/cpu_topology.py` module replaces the naive assumption that `os.cpu_count()` tells a process how many cores it can actually use. That assumption is false in exactly the environments this project targets in production: Docker, Kubernetes, and most managed hosting (including Streamlit Community Cloud) enforce a **cgroup CPU quota** that `os.cpu_count()` cannot see — a container capped at 1-2 vCPUs on a 64-core host still reports 64 from `os.cpu_count()`, and every worker process independently spinning up a full-width BLAS/torch thread pool against that phantom core count is one of the most common real-world causes of CPU-inference thread oversubscription and unpredictable p95 latency under load in containerized ML deployments.

`discover_cpu_topology()` resolves `effective_cores` as the *minimum* of three independently-binding signals, most-authoritative first: (1) cgroup CPU quota (`cpu.max` on cgroup v2, `cpu.cfs_quota_us`/`cpu.cfs_period_us` on v1) — the actual container-enforced limit; (2) the process's CPU affinity mask via `os.sched_getaffinity` (Linux-only; respects `taskset`/`cpuset`/SLURM pinning that `os.cpu_count()` also ignores); (3) the host's raw logical core count as the final fallback. Fractional quotas floor down (2.9 cores -> 2), and the result floors at 1. This mirrors the same container-aware resolution strategy used by the JVM's `-XX:ActiveProcessorCount` auto-detection and Ray's/HuggingFace's own cgroup-aware worker sizing — not a bespoke heuristic. A companion `recommended_thread_env()` returns `OMP_NUM_THREADS`/`MKL_NUM_THREADS`/`OPENBLAS_NUM_THREADS`/`NUMEXPR_NUM_THREADS`/`TOKENIZERS_PARALLELISM` set to the effective core count — the standard fix for BLAS thread oversubscription — and deliberately does **not** invent a `TORCH_NUM_THREADS` env var (PyTorch has none; callers must call `torch.set_num_threads(topology.effective_cores)` explicitly).

`HardwareSnapshot` gained a `cpu_topology: CPUTopology` field (auto-populated via `discover_cpu_topology()` when not explicitly supplied). `profiles.resolve_profile()` now also forces `CPU_MINIMAL` (or `REMOTE_LLM` if configured) when `effective_cores <= DEFAULT_LOW_CORE_THRESHOLD` (2), independent of RAM — a RAM-rich but CPU-quota-starved container is still CPU-constrained. `budgets.budget_for_profile()` gained an optional `cpu_topology` argument that scales `max_workers` from `effective_cores`, clamped to a profile-specific `[min, max]` range (`BALANCED`: 2-8, `ACCELERATED`: 2-6, `REMOTE_LLM`: 4-16 with a 2x I/O-bound multiplier; `CPU_MINIMAL` stays pinned at 1 regardless of core count, since that profile is chosen specifically because hardware is constrained). Calling `budget_for_profile(profile)` without `cpu_topology` returns the unchanged static baseline, preserving prior deterministic behavior for callers that haven't wired hardware discovery through yet.

Consequence: real dev/CI sandboxes are frequently affinity-limited to 1 core (confirmed by running `discover_cpu_topology()` in this project's own CI sandbox during implementation — it reported `effective_cores=1` via the `affinity_mask` signal), which is exactly the scenario this module exists to catch rather than a test artifact. `tests/test_execution_profiles.py`'s snapshot fixtures were updated to pass an explicit "ample cores" `CPUTopology` so hardware-agnostic assertions stay deterministic regardless of what host the suite runs on. 24 new tests added across `tests/test_cpu_topology.py` and the extended `tests/test_resource_budgets.py`/`tests/test_execution_profiles.py`; full suite (209 tests) passes clean with no regressions.
