# Legal Intelligence Evaluation Matrix v1

## Goal

Measure the system as a legal intelligence engine rather than treating retrieval Recall@K as proof of legal understanding.

## Tracks

| Track | What it measures | Primary metrics | Gate |
|---|---|---|---|
| Retrieval | Finds relevant legal material | MRR, Recall@1/3/5/10 | Must not regress protected baseline |
| Full Retrieval | Finds all evidence needed by a question | Full Recall@K, set recall | New primary IR quality signal |
| Query Understanding | Maps natural-language questions to legal concepts | intent/domain/jurisdiction/date accuracy | Human-labelled benchmark |
| Entailment | Evidence actually supports the claim | entailment accuracy, contradiction rate | Critical |
| Grounded Generation | Answer stays inside evidence | citation precision/recall, unsupported-claim rate | Critical |
| Legal Reasoning | Applies rules to facts | exact/semantic rubric + human score | Human/legal review |
| Temporal | Uses the legally effective version | temporal accuracy, supersession errors | Critical |
| Jurisdiction | Uses the correct legal system | jurisdiction accuracy, contamination rate | Critical |
| Abstention | Refuses unsupported conclusions | precision/recall of abstention, false-confidence rate | Critical |
| Arabic Robustness | Handles Arabic variation | normalization/paraphrase robustness | Required |
| Efficiency | Produces quality within hardware budget | p50/p95 latency, RAM, VRAM, CPU, cost | Required |
| Reliability | Recovers from failures safely | recovery rate, MTTR, graceful-degradation rate | Required |

## Dataset splits

The benchmark must maintain separate datasets for:

- `train`: allowed for model adaptation when justified;
- `validation`: tuning and model selection;
- `test`: locked evaluation;
- `challenge`: adversarial and out-of-distribution cases;
- `production_feedback`: post-release cases that cannot silently become training data.

Splitting must consider legal identity, document version, jurisdiction, case family, and near-duplicate text. A random row split is not sufficient when the same legal source can appear in multiple forms.

## Query families

The Egyptian benchmark should contain at least:

1. direct article lookup;
2. paraphrase;
3. Egyptian colloquial wording;
4. multi-article questions;
5. exceptions and negation;
6. fact-pattern questions;
7. temporal/version questions;
8. cross-reference questions;
9. conflicting-authority questions;
10. insufficient-evidence questions;
11. distractor-heavy questions;
12. jurisdiction-sensitive questions.

## Required annotations

For each benchmark item, where available:

- query;
- jurisdiction;
- legal domain;
- effective date;
- relevant document IDs;
- relevant article IDs;
- evidence spans;
- expected legal proposition;
- contradiction/counter-evidence;
- abstention expected;
- answer rubric;
- annotation provenance;
- annotator agreement.

## Evaluation rule

A benchmark score must always include dataset version, corpus version, model version, retriever version, reranker version, prompt/config version, and runtime profile. No score is valid without reproducibility metadata.

## Current baseline interpretation

The existing v3 self-retrieval smoke set is retained as a regression guard only. It must not be described as proof of Egyptian legal understanding because its queries are derived from the source article text.

## Future external references

Use established Arabic legal benchmarks such as ArabLegalEval and ALARB as methodology/reference points. Do not treat another jurisdiction's benchmark score as evidence of Egyptian legal competence. ArabLegalEval provides multitask Arabic legal evaluation, while ALARB emphasizes multi-step reasoning over Arabic commercial court cases. citeturn216610search0turn216610search5

Use COLIEE-style statute retrieval principles for multi-evidence evaluation: when multiple legal articles are required to answer a query, the complete relevant set matters, not only the first relevant hit. citeturn216610search13
