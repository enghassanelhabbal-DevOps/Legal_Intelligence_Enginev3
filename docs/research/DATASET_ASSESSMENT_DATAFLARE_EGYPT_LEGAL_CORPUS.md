# Dataset Assessment — dataflare/egypt-legal-corpus

Status: Proposed external dataset for Stage 1 intake/evaluation
Date: 2026-08-28

## Executive assessment

`dataflare/egypt-legal-corpus` is a strong candidate for the Legal Intelligence Engine's **Egyptian legal knowledge/domain corpus**, but it must NOT be treated automatically as a retrieval benchmark, legal-reasoning benchmark, or fine-tuning dataset.

Current public dataset metadata reports:

- one `train` split;
- approximately 2,434 records;
- 25,054,372 tokens according to the dataset card;
- Arabic legal text;
- fields: `law_name`, `categories`, `text`, `tokens`;
- hierarchical categories;
- MIT license stated by the dataset card;
- version 1.0 dated January 2026.

These facts come from the public dataset card and are subject to independent intake verification.

## Real sample findings (n=10, viewer page 1 of 25) — 2026-08-28 update

Programmatic download (`datasets.load_dataset`) is not reachable from the implementation sandbox (network egress restricted to package registries; `huggingface.co` is not allowlisted there). The dataset's public web viewer *is* reachable through a separate fetch path, and returned 10 real rows. This is a genuine but partial sample (10 of 2,434 records, ~0.4%) — findings below are evidence, not corpus-wide statistics, and must be re-verified once full ingestion is possible.

**1. Confirmed real overlap with the existing 952-article corpus.** Row 6 is `قانون الإجراءات الجنائية` (Criminal Procedures Code) — one of the exact two laws already in `legal_documents.json`. This directly enables Experiment E (overlap analysis) once full ingestion is possible. Note: this is the Criminal Procedures law, which already has populated `article_id` in the existing corpus — so this specific row does not by itself help recover the Penal Code's missing `article_id` (DR-018); the Penal Code (`قانون العقوبات`) did not appear in this 10-row sample, so its presence/absence in Dataflare is still unconfirmed.

**2. A real, previously-unknown data-quality defect: probable OCR/extraction noise prefixed to record text.** Multiple, unrelated records open with a short meaningless token followed by a small number, before any real legal content:

```text
"دودو 10 قانون الاجراءات الجنائية طبقا لاحدث التعديلات..."
"دودو 4 قانون المحاماة والادارات القانونية..."
"دودو 3 قانون الاثبـات..."
"دودو 5 امر خروج نهائي مجموعة..."
"048 بونو 1 وين 1 المواعيد والمدد القانونية..."
```

The repeated `"دودو <N>"` pattern across otherwise-unrelated laws is consistent with a systematic extraction artifact (e.g. a misread page stamp or scanner signature), not legal content. A detector (not a silent fixer — see `src/legal_ai/ingestion/text_quality_diagnostics.py`) was built and tested against these exact observed strings. This must be re-run against the full corpus at real ingestion to establish true prevalence before any cleaning step is designed; a 10-row sample is not enough to design a safe strip rule.

**3. Category field is real but observed far less granular than the dataset card's own example suggests.** The card's example shows a 2-level hierarchy (`["القوانين الاجتماعية", "قانون الطفل"]`), but 8 of the 10 real sampled rows share the single generic category `["الاكواد الجزء الاول"]` ("Codes, Part One"). Only 2 distinct category values appear across the 10-row sample. This is a real signal, not a rejection of H3 (metadata-aware pruning) — but it means H3's minimum evidence bar must include measuring category-field cardinality across the full corpus before assuming category is a useful pruning filter; on this sample alone it would barely discriminate anything.

**4. Record sizes are confirmed enormous, validating the hierarchical-chunking necessity as non-optional.** Observed token counts in the sample range 19,266–192,818 tokens per record (one entire Civil Code as a single row). This is not a design assumption anymore — it is measured. Feeding a 192K-token record directly into any embedding model is not a viable option under this project's stated resource constraints; hierarchical chunking (H2) is a prerequisite for using this dataset at all, not an optimization.

These four findings are strong enough to change the assessment's confidence but not its conclusion: **the dataset remains a strong candidate for the knowledge corpus role**, with two new concrete pre-ingestion tasks added to the processing plan below (noise-prefix prevalence measurement; category cardinality measurement).

## Full corpus archaeology (real data, 2026-08-28) — supersedes the 10-row sample above

The person uploaded the actual parquet file (`train-00000-of-00001.parquet`, 24.9MB, SHA-256 `a55c349e...`, snapshotted to `data/raw/dataflare/`). All 2,434 records / 25,054,372 tokens were analyzed directly — this section reports measured facts, not sampled estimates.

**1. The corpus is 86.7% case law, not statutes — this changes the product framing.** 2,110 of 2,434 records (15.55M of 25.05M tokens) are Egyptian Court of Cassation (محكمة النقض) ruling excerpts, identifiable by the citation pattern `"الطعن رقم N لسنة Y مكتب فنى O صفحة رقم P بتاريخ DATE"`. Only 324 records (9.5M tokens) are primary legislation. The `law_name` field is overloaded: for statutes it's the law's title; for case rulings it's actually a **legal doctrine/topic label** (e.g. `"المنع من سماع الدعوى"` — "barring the hearing of a claim"), which is why 412 "law names" appeared to repeat in the earlier duplicate-count check — they're topic labels shared across many distinct rulings, not duplicate laws.

This is a genuinely positive finding for the product thesis, not a downgrade: case-ruling excerpts are exactly the citable, evidence-grounded precedent units H4 (evidence-span groundedness) needs. A citation extractor (`src/legal_ai/ingestion/case_citation_extraction.py`) was built and validated: **94.8% of case-ruling records (1,998 of 2,108) extract a clean, complete citation** (appeal number, year, technical office, page, date) — a strong, real evidence base for a "here's the exact precedent this answer is grounded in" feature.

**2. 28.6% of records are exact-duplicate content (696 of 2,434, in 347 groups).** This must be deduplicated before any train/eval split — duplicate groups sharing the same citation and text would trivially leak across a naive random split. The existing group-safe split design (`leakage.py`, DR-017) already handles this correctly if the grouping key is the case citation for rulings (not `law_name`, which is a shared topic label across many distinct rulings and would incorrectly lump unrelated cases into one leakage group).

**3. The article-boundary segmenter initially failed on 99.7% of real statute records — root cause found and fixed.** `article_segmentation.py` was built and tested only against synthetic fixtures with newline-separated articles. Real Dataflare statute text is a **single continuous flattened paragraph with no internal newlines at all** — e.g. `"...احكام عامة مادة 1 تسرى قوانين المرافعات... مادة 2 كل اجراء..."`, all on one line. The segmenter's line-start anchor requirement made it blind to this. Fixed by matching `"مادة N"`/`"المادة N"` anywhere in text, with a same-token/fused-preposition exclusion for referential mentions (`"طبقا للمادة 5"` referencing article 5, not introducing it) so references aren't double-counted as boundaries. **Post-fix: 17.2% of statute records (56 of 326) still report zero markers** — inspection confirmed these are not segmenter failures but genuinely structure-less content: lawsuit petition templates, legal notice forms, and explanatory/textbook-style prose that legitimately has no article numbering. The segmenter correctly reports zero rather than forcing false structure. Mean text-coverage when markers are found: 85.7%.

**4. The noise-prefix pattern (DR-020) is real but much rarer at full scale than the 10-row sample suggested: 0.86% (21 of 2,434), not ~50%.** The earlier 10-row sample was not representative — a real, if uncomfortable, reminder that a 0.4% sample can substantially mislead on prevalence even when the pattern itself is genuinely present. DR-020's decision (flag, don't silently strip) stands, now grounded in an accurate prevalence figure.

**5. Category field is far richer at full scale than the 10-row sample suggested: 171 distinct category values across 6,769 tags, zero records with no category.** The earlier "category field looks too coarse for H3" concern was also a sampling artifact — top categories (`النقض و المحكمة الادارية`: 2,051 uses; `نقض مدني جزء اول`: 1,293; `إيجار`: 182; `أحوال شخصية للمسلمين`: 82, etc.) show genuine, usable taxonomic signal. H3 (metadata-aware pruning) is more promising than the earlier sample suggested — reflected in `docs/research/RESEARCH_HYPOTHESES.md`.

**6. Zero exact-text overlap with the existing 952-article corpus** (`legal_documents.json`). This is expected, not a leakage-safety green light by itself: Dataflare stores each law as one giant record while the existing corpus stores one record per article, so exact full-text matching structurally cannot find overlap even where the same law is genuinely present in both. Confirmed: Dataflare does contain a Penal Code entry, but it is titled `"نموذج كــود قانون العقوبات"` ("Model Code draft of the Penal Code" — note the decorative tatweel-stretched `"كــود"`, another text-quality artifact), not confirmed identical in content or authority to the production Penal Code already in `legal_documents.json`. **This revises DR-018's proposed remediation path**: recovering the missing Penal Code `article_id` values by cross-referencing against Dataflare requires (a) fuzzy/substring matching at the article-segment level, not exact full-text matching, and (b) verifying the Dataflare "Model Code" entry is legally equivalent to the production law before trusting it as a recovery source — it is not a guaranteed win the way DR-018 originally framed it.

**7. Arabic orthographic normalization is a confirmed, not hypothetical, blocker for any name-based matching between datasets.** Root-caused directly: the corpus uses **decomposed Arabic hamza combining marks** (U+0655 ARABIC HAMZA BELOW, U+0654 ARABIC HAMZA ABOVE as separate combining characters) rather than precomposed letters (إ U+0625, ئ U+0626). Standard Unicode NFC normalization does **not** fold these — verified directly (`unicodedata.normalize('NFC', ...)` on a real `law_name` value did not produce a match against the precomposed form). Any join between Dataflare and the existing corpus by law name must go through the project's existing Arabic-specific normalization pipeline (`ingestion/normalization.py`), not naive string comparison — this is now evidence, not a general Arabic-NLP truism asserted without proof.

## Why this dataset is strategically valuable

The dataset is materially different from a small article-level corpus. The public examples show records that can contain substantial portions of complete laws or long legal texts. This gives us a useful opportunity to build a **document → section/chapter → article → paragraph** hierarchy rather than treating every row as a retrieval unit.

That matters because the product goal is not only semantic similarity. We need legal identity, article boundaries, authority, versioning, and evidence spans.

## Critical caveats

### 1. One train split is not a benchmark

The public release does not provide a protected user-style validation/test split. We must create our own evaluation assets and protect them from tuning.

### 2. Metadata is insufficient for legal version intelligence

The public schema exposes `law_name`, `categories`, `text`, and `tokens`, but does not by itself establish effective dates, amendment chains, repeal dates, authority level, official source URLs, or version identifiers.

Those must be derived or enriched only from verified provenance; never guessed.

### 3. License is not the same as source provenance

The dataset card states MIT and allows academic/commercial use. We still need provenance validation at dataset intake and, where practical, source-level verification. A repository-level license declaration must not be used as proof that every source text has identical provenance or that downstream obligations are absent.

### 4. Likely overlap with existing Egyptian corpus must be measured

The Engine already has an approximately 952-article Egyptian corpus. We must measure document/law/article overlap before assigning roles or creating train/test splits.

### 5. Long records change retrieval design

Rows can be very large. Feeding whole records directly into embeddings or reranking would waste memory and reduce retrieval precision. We need hierarchical chunking with stable legal identities and parent-child provenance.

## Recommended role assignment

Initial recommendation:

| Role | Recommendation |
|---|---|
| Egyptian knowledge corpus | **YES — primary candidate** |
| Ingestion/parser validation corpus | **YES** |
| Retrieval tuning | **POSSIBLE after provenance/overlap audit** |
| Reranker tuning | **POSSIBLE, derived subsets only** |
| Legal reasoning training | **NOT YET** |
| Final retrieval benchmark | **NO** unless held-out labels are independently created |
| Final legal-understanding benchmark | **NO** unless expert questions/labels are created |
| Challenge/adversarial set | **Derived later, separately protected** |
| Fine-tuning/SFT | **DEFER** until measured failure analysis justifies it |

## Stage 1 processing plan

```text
Hugging Face dataset
  ↓
Immutable source snapshot + commit/revision identifier
  ↓
Dataset manifest
  ↓
Schema validation
  ↓
Text integrity checks
  ↓
Extraction-noise prevalence scan (NEW — see "Real sample findings")
  ↓
Unicode/Arabic diagnostics
  ↓
Law identity extraction
  ↓
Document-level grouping
  ↓
Article/section structure extraction
  ↓
Category-field cardinality audit (NEW — see "Real sample findings")
  ↓
Duplicate + near-duplicate analysis
  ↓
Overlap analysis vs existing 952-article corpus
  ↓
Provenance/license evidence
  ↓
Temporal metadata audit
  ↓
Task-role assignment
  ↓
Safe split planning
  ↓
Knowledge-release candidate
```

## Hierarchical legal representation

Do NOT flatten the new corpus directly into generic chunks.

Preferred logical hierarchy:

```text
Law
 └── Version (when verifiable)
      └── Part / Book / Chapter / Section
           └── Article
                └── Paragraph / Clause
                     └── Retrieval chunk
```

Every derived chunk should retain stable parent identity where available.

Recommended identifiers:

- `dataset_id`
- `dataset_version`
- `law_id`
- `document_id`
- `article_id`
- `section_id`
- `chunk_id`
- `parent_id`
- `content_hash`
- `source_hash`

## Retrieval research enabled by this dataset

This dataset is particularly useful for testing the difference between:

1. **document retrieval** — identify the correct law;
2. **section retrieval** — identify the correct structural region;
3. **article retrieval** — identify the relevant article(s);
4. **passage retrieval** — identify the exact supporting span;
5. **multi-evidence retrieval** — identify the complete set of relevant authorities.

This gives us a research path toward a hierarchical retrieval architecture rather than one flat vector index.

## Proposed experiments

### Experiment A — Flat vs hierarchical retrieval

Compare:

```text
Flat chunk index
vs
Law → section → article → passage retrieval
```

Measure Recall@K, Full Recall@K, latency, and memory.

### Experiment B — Metadata-aware retrieval

Use category and law identity only as explicit metadata features/filters, not as a substitute for semantic relevance.

### Experiment C — Article-number retrieval

Create queries using multiple forms:

- `المادة 42`
- `مادة 42`
- `42`
- natural-language reference to the same article.

Measure robustness separately from semantic retrieval.

### Experiment D — Long-document evidence extraction

For very long laws, test whether hierarchical narrowing reduces reranker workload while preserving evidence recall.

Expected benefit: lower CPU/RAM/latency pressure and less noisy candidate context.

### Experiment E — Existing 952 corpus comparison

Measure overlap and disagreement between the existing corpus and Dataflare corpus at:

- law level;
- article level;
- normalized text level;
- hash level;
- near-duplicate level.

Do not assume one corpus is better because it is larger.

## Dataset-to-benchmark strategy

The strongest benchmark should NOT simply sample random rows from this corpus.

Instead build a separate benchmark layer:

```text
Authoritative legal corpus
        ↓
Human/query generation
        ↓
Independent gold evidence
        ↓
Protected benchmark
```

Suggested Egyptian benchmark categories:

- direct article lookup;
- paraphrase;
- colloquial user phrasing;
- fact pattern;
- multi-article question;
- rule + exception;
- historical/as-of-date;
- contradiction/conflict;
- insufficient evidence;
- jurisdiction confusion (later when additional jurisdictions exist).

## Training recommendation

Do not fine-tune the base LLM directly on the full 25M+ token corpus as the first action.

The corpus is more valuable initially as a **knowledge and evaluation substrate**.

Only consider continued pretraining/domain adaptation/SFT after experiments establish a failure mode that retrieval, evidence selection, prompting, or model routing cannot reasonably solve.

If training becomes justified, build the training set from explicitly licensed and de-leaked subsets with semantic grouping and a protected held-out benchmark.

## Resource strategy

Because records can be large, Stage 1 implementation should avoid loading the entire corpus into multiple in-memory representations.

Prefer:

- streaming/iterative reads;
- Arrow/Parquet-native processing;
- bounded worker pools;
- one-pass statistics where possible;
- content hashes instead of retaining full duplicate strings when practical;
- lazy text materialization;
- chunk-level persistence;
- no model loading during metadata-only profiling.

## Legal intelligence opportunity

This dataset can support a major architectural improvement: **legal-structure-aware retrieval**.

Instead of asking only:

> Which chunk is semantically closest to the query?

we can ask:

> Which law, structural location, article, version, and exact span provide the strongest complete evidence for this question?

That directly supports the product's long-term evidence-first goal.

## Required intake outputs

The Stage 1 adapter should produce:

1. dataset manifest;
2. reproducible source snapshot/revision metadata;
3. schema profile;
4. Arabic quality profile;
5. law/document inventory;
6. duplicate/near-duplicate report;
7. overlap report against the existing corpus;
8. provenance/license assessment;
9. candidate role assignment;
10. proposed split manifest;
11. chunking/structure manifest;
12. resource report;
13. acceptance/rejection decision with reasons.

## Decision gate

**Current decision: ACCEPT FOR STAGE 1 INTAKE/AUDIT.**

**Do not yet accept for training, final benchmarking, or production knowledge release** until the intake pipeline verifies the dataset revision, provenance, schema, overlap, legal structure, and release integrity.

## External reference

Public dataset card:
`https://huggingface.co/datasets/dataflare/egypt-legal-corpus`

The public card states 2,434 examples, 25,054,372 tokens, fields `law_name/categories/text/tokens`, Arabic language, and an MIT license. These are external claims that must be reproduced by our own Stage 1 intake artifacts before being treated as project evidence.
