# Data Governance — Legal Intelligence Platform

## 1. Purpose

Define how legal corpora, evaluation datasets, training data, generated artifacts, and failure-derived cases enter and move through the system without semantic corruption, licensing mistakes, contamination, or benchmark leakage.

## 2. Dataset roles

Each dataset MUST have one or more explicit roles:

- `knowledge_corpus`
- `retrieval_tuning`
- `retrieval_training`
- `reranker_tuning`
- `reranker_training`
- `reasoning_sft`
- `validation`
- `heldout_test`
- `challenge_adversarial`
- `benchmark_only`
- `failure_regression`

Role assignment is metadata, not an assumption made by file location alone.

## 3. Intake record

Every dataset intake should record:

```text
DatasetID
Version
Owner/source
Acquisition date
License / usage rights
Provenance URL or source reference
Language(s)
Jurisdiction(s)
Legal time coverage
Document count
Record count
Schema
Authority distribution
Annotation method
Annotation quality evidence
Known limitations
Intended roles
Hash / fingerprint
```

No production use before the intake record exists.

## 4. Source authority

Classify source authority explicitly:

1. official primary legal source;
2. official judicial source;
3. official regulatory/administrative source;
4. reputable secondary legal source;
5. user/private material;
6. unknown/unverified.

Authority classification must never be inferred solely from wording.

## 5. Legal text preservation

For each legal source preserve the original content exactly where licensing and storage policy permit.

Derived representations may include:

- Unicode-normalized text;
- retrieval-normalized text;
- tokenized text;
- embedding text;
- structural fields;
- extracted citations.

Derived representations must never replace the canonical raw source for citation/display purposes.

## 6. Validation

Before indexing:

- validate schema;
- validate required identifiers;
- detect malformed records;
- validate jurisdiction values;
- validate date formats;
- detect impossible temporal ranges;
- detect duplicate IDs;
- compute content/document hashes;
- inspect empty/near-empty records;
- detect OCR corruption where applicable;
- preserve quality warnings.

Invalid records are quarantined rather than silently repaired when repair could alter legal meaning.

## 7. Deduplication

Use multiple levels:

```text
exact ID duplicate
→ exact content duplicate
→ normalized-content duplicate
→ near-duplicate candidate
```

Near-duplicate detection must not automatically merge documents when different versions, amendments, jurisdictions, or authorities may be legally meaningful.

## 8. Leakage control

Evaluation contamination is a release-blocking risk.

Check overlap at:

- document level;
- article level;
- law level;
- source level;
- normalized text level;
- semantic near-duplicate level where practical.

Prefer splitting by law/source rather than random rows when the same legal material appears in multiple forms.

The final held-out benchmark MUST NOT be used for:

- training;
- fine-tuning;
- prompt selection;
- threshold selection;
- retrieval-weight selection;
- model selection.

## 9. Dataset splits

Recommended partitions:

```text
TRAIN / TUNE
  ↓
VALIDATION
  ↓
HELD-OUT TEST
  ↓
CHALLENGE / ADVERSARIAL
```

For legal text, a source- or law-level split is preferred over a random row split when overlap exists.

## 10. Annotation protocol

Human/expert annotations should define:

- question;
- relevant authority set;
- evidence role;
- expected legal issue;
- applicable rule;
- exceptions;
- required facts;
- jurisdiction;
- reference date;
- answer constraints;
- abstention condition.

Annotator guidance MUST distinguish:

`relevance` from `legal support` from `correct final answer`.

Inter-annotator disagreement should be tracked rather than hidden.

## 11. Arabic legal data

Test and document:

- orthographic variants;
- diacritics/tatweel;
- spelling noise;
- Arabic punctuation;
- Arabic numerals and Western numerals;
- article numbering formats;
- Arabic/English mixed content;
- abbreviations;
- legal synonyms;
- paraphrases;
- realistic colloquial queries.

Never normalize away distinctions that alter legal identity or source citation.

## 12. Knowledge release

A legal knowledge release is an immutable logical package containing:

- corpus manifest;
- source authority metadata;
- version graph metadata;
- normalized representations;
- index identifiers;
- release configuration;
- quality report;
- evaluation result;
- content hash;
- release timestamp/identifier.

Publish atomically only after the relevant gates pass.

## 13. Dataset versioning

Every changed dataset creates a new dataset version. Do not overwrite a benchmark dataset in place.

At minimum record:

```text
parent_version
change_reason
added_count
removed_count
modified_count
hash_before
hash_after
validation_report
benchmark_delta
```

## 14. Failure-derived data

Operational failures can become regression cases only after sanitization and review.

Never automatically promote raw production user content into training data.

Failure case record:

```text
failure_id
sanitized_input
expected_behavior
actual_behavior
failure_class
software_version
model_version
knowledge_release
hardware_profile
recovery_action
human_review_status
regression_status
```

## 15. Privacy and sensitive content

Treat uploaded legal documents, case facts, names, IDs, contacts, financial information, and client materials as potentially sensitive.

Development datasets should be minimized or anonymized where possible. Production customer content must not be reused for training without an explicit lawful/contractual basis and governance process.

## 16. Data quality score

A dataset quality report SHOULD score at least:

```text
schema_quality
provenance_quality
authority_quality
language_quality
jurisdiction_quality
temporal_quality
dedup_quality
annotation_quality
leakage_risk
completeness
```

The score is decision support, not a substitute for human review.

## 17. Intake gate

A dataset can enter the system only when:

- provenance is known;
- use rights are understood;
- schema is mapped;
- jurisdiction/language are known;
- temporal semantics are understood;
- duplicates are measured;
- leakage risk is assessed;
- role is assigned;
- quality warnings are recorded;
- a reproducible version identifier exists.
