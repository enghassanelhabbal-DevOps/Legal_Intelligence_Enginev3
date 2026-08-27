# Legal AI Evaluation Blueprint

## Purpose

Transform the current retrieval regression checks into a research-grade, product-grade evaluation system for Egyptian and Arabic legal intelligence.

The engine must be evaluated as multiple separable capabilities. A single retrieval score or a single answer-accuracy score is not sufficient.

## Evaluation layers

### 1. Ingestion integrity

Measure whether source material is parsed, normalized, deduplicated, versioned, and attributed without destructive changes.

Metrics:
- document preservation rate
- metadata completeness
- duplicate detection precision/recall
- article-boundary accuracy
- source/provenance coverage
- version-link correctness

### 2. Retrieval

Measure whether the engine retrieves all legally relevant material, not merely one similar article.

Primary metrics:
- Recall@1, @3, @5, @10
- MRR
- nDCG@k when graded relevance exists
- Full Recall@k for multi-article questions
- candidate recall before reranking
- dense preservation rate

Required query classes:
- exact article reference
- lexical paraphrase
- semantic paraphrase
- colloquial Arabic question
- formal legal Arabic question
- long fact pattern
- multi-article question
- cross-document question
- ambiguous question
- negative/no-answer question

### 3. Reranking

Measure whether reranking improves ordering without destroying candidate recall.

Metrics:
- MRR delta
- nDCG@k delta
- Recall@k delta
- latency p50/p95
- CPU/RAM/VRAM peak

The protected baseline must be compared before/after every ML change.

### 4. Evidence selection

Measure whether the evidence set is sufficient, minimal, diverse, and legally attributable.

Metrics:
- evidence recall
- evidence precision
- citation coverage
- unsupported-claim rate
- redundant-evidence rate
- evidence set size

### 5. Legal understanding

Evaluate the model/system independently from retrieval by supplying golden evidence.

Task families:
- legal issue identification
- rule identification
- exception identification
- temporal applicability
- distinction between similar provisions
- procedural sequencing
- contradiction detection
- entailment / non-entailment
- uncertainty / abstention

This separates retrieval failures from reasoning failures.

### 6. Grounded generation

Evaluate the final response only against the retrieved evidence and the legal gold answer.

Metrics:
- citation validity
- claim-level support rate
- contradiction rate
- unsupported assertion rate
- answer completeness
- legal conclusion accuracy
- abstention quality
- format/schema validity

Never use a single LLM-judge score as the only production metric.

### 7. Arabic robustness

Create paired/variant queries for:
- spelling variants
- alef variants
- ya/alef-maqsura variants
- optional diacritics
- tatweel
- punctuation variation
- Arabic/English mixed legal terminology
- common user phrasing
- formal legal Arabic
- colloquial Egyptian Arabic

Measure score stability across variants.

### 8. Jurisdiction safety

The engine must not silently answer from the wrong jurisdiction.

Create adversarial tests where:
- Egypt and Saudi provisions have similar wording
- the same legal term means different things across jurisdictions
- a document from another jurisdiction is semantically stronger but legally invalid for the requested jurisdiction

Metric:
- jurisdiction leakage rate

### 9. Temporal/version safety

Questions must specify dates when relevant.

Create cases for:
- law amended after the relevant date
- repealed article
- superseded provision
- transitional provisions
- historical law vs current law

Metrics:
- temporal correctness
- effective-version selection accuracy
- stale-citation rate

### 10. Failure and recovery

Every runtime failure becomes structured telemetry and, where appropriate, a regression case.

Failure classes:
- OOM
- model load failure
- corrupted index
- missing artifact
- malformed document
- invalid citation
- provider timeout
- provider rate limit
- partial dependency failure
- resource exhaustion

Measure:
- recovery success rate
- graceful-degradation rate
- retry amplification
- mean recovery time
- repeated-failure recurrence

## Dataset strategy

Do not create one giant train/test split and report one score.

Maintain separate immutable sets:

- `retrieval_train`
- `retrieval_validation`
- `retrieval_test`
- `reasoning_validation`
- `reasoning_test`
- `temporal_test`
- `jurisdiction_test`
- `arabic_robustness_test`
- `adversarial_test`
- `production_shadow_set`

### Split policy

Prefer grouping by legal source/law/case family when leakage is possible. Random row-level splitting is unsafe when near-duplicate articles, versions, templated questions, or the same legal source occur in multiple splits.

Test labels must not be used to tune retrieval weights, thresholds, prompts, or model selection.

## Golden annotation schema

Each human-labeled query should support multiple relevant documents and graded relevance when possible:

```json
{
  "query_id": "EG-IR-0001",
  "jurisdiction": "EG",
  "question": "...",
  "effective_date": "2024-01-01",
  "relevant_documents": [
    {"document_id": "...", "relevance": 3, "role": "primary"},
    {"document_id": "...", "relevance": 2, "role": "supporting"}
  ],
  "must_include": ["..."],
  "must_not_use": ["..."],
  "gold_answer": "...",
  "legal_issues": ["..."],
  "annotation_notes": "..."
}
```

## Annotation workflow

Use at least two independent reviewers for high-risk legal gold labels where feasible, followed by adjudication for disagreements.

Track:
- reviewer IDs as opaque identifiers
- annotation version
- disagreement type
- adjudication outcome
- source authority

Do not expose private reviewer information in model outputs.

## External benchmark alignment

Use ideas from COLIEE-style legal retrieval and entailment, especially the requirement to retrieve all relevant articles where multiple articles are needed and the separation between retrieval and entailment. See `docs/RESEARCH_REFERENCES.md` when added.

For Arabic legal reasoning, use ArabLegalEval and ALARB as external references, but do not treat them as substitutes for an Egypt-specific benchmark.

## Release gates

A release cannot ship solely because answer quality looks good.

Minimum gates:

1. retrieval regression gate passes
2. evidence support rate does not regress
3. jurisdiction leakage is below threshold
4. temporal error rate is below threshold
5. schema/citation validation passes
6. no unresolved critical security failures
7. resource budget remains within the configured profile
8. recovery tests pass for supported failure classes

Thresholds must be stored in versioned configuration, not hard-coded in evaluation scripts.
