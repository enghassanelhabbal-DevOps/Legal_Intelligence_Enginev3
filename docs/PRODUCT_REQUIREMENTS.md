# Product Requirements — Legal Intelligence Platform

## 1. Product vision

Build an evidence-first Legal Intelligence Platform that helps professional users research and analyze Egyptian law using authoritative, traceable, version-aware evidence.

The product is not positioned as a generic conversational assistant. Chat is only one interface. The durable product value is the legal intelligence pipeline beneath it.

## 2. Problem

Legal users need fast answers but cannot safely rely on unsupported model prose. The system must reduce research time while preserving source traceability, jurisdiction correctness, temporal correctness, and uncertainty.

## 3. First customer segment

Primary:
- lawyers;
- legal researchers;
- legal operations teams;
- compliance/regulatory professionals.

Secondary later:
- law students and academics;
- enterprise knowledge teams;
- LegalTech platforms consuming the engine through API.

## 4. First product wedge

### Egyptian Legal Research + Evidence Report

Input:
- natural-language legal question;
- optional facts;
- optional jurisdiction;
- optional as-of date;
- optional requested authority type.

Output:
- concise answer;
- applicable legal rules;
- supporting authorities;
- counter/contradictory authorities when found;
- evidence excerpts;
- exact citations;
- legal-version/date context;
- uncertainty and missing-evidence warnings.

## 5. Core user jobs

### Research
Find the best primary legal authorities for a question.

### Explain
Explain what an identified article/rule means using the source text.

### Apply
Map supplied facts to legal rules without inventing facts.

### Compare
Compare legal treatment across explicitly selected jurisdictions.

### Historical research
Answer what rule applied at a specified date.

### Audit
Show why an answer was produced and which evidence supported each material proposition.

## 6. Non-goals for the first commercial version

- autonomous legal representation;
- automated filing or court submission;
- autonomous legal decision-making;
- unrestricted web browsing as a source of authority;
- silent cross-jurisdiction reasoning;
- replacing professional legal judgment;
- self-modifying production behavior.

## 7. Product principles

1. Evidence precedes generation.
2. Primary authority is preferred where available and identifiable.
3. Legal versions are explicit.
4. Jurisdiction is explicit.
5. Unsupported claims are failures.
6. The product can abstain.
7. Every important result is auditable.
8. Resource use is bounded and measurable.
9. Product quality is benchmarked, not inferred from demos.
10. New legal knowledge normally enters through the knowledge lifecycle, not LLM retraining.

## 8. Functional requirements

### FR-01 Query intake
The system accepts Arabic legal questions and later bilingual questions.

### FR-02 Query understanding
Extract language, jurisdiction, legal domain, temporal constraint, intent, question type, and required authority classes without inventing facts.

### FR-03 Retrieval
Run lexical and dense retrieval with configurable candidate limits.

### FR-04 Filtering
Apply jurisdiction, legal-version, source-authority, and other explicit metadata filters.

### FR-05 Reranking
Score the candidate pool using a replaceable reranker.

### FR-06 Evidence construction
Build a bounded EvidenceSet with complete provenance.

### FR-07 Support checking
Determine whether evidence directly supports, partially supports, contradicts, or fails to support a material claim.

### FR-08 Generation
Produce grounded structured output from bounded evidence.

### FR-09 Abstention
Abstain or warn when evidence is insufficient, ambiguous, contradictory, stale, or out of scope.

### FR-10 Audit
Persist enough metadata to reproduce the legal answer path without persisting unnecessary sensitive data.

## 9. Quality requirements

### Correctness
The engine must not fabricate authorities, articles, dates, or legal relationships.

### Relevance
Retrieved evidence should cover the necessary legal material, including multi-article cases.

### Grounding
Material claims must map to evidence identifiers.

### Robustness
The system should tolerate normal Arabic spelling and formatting variation.

### Reliability
Common runtime failures should recover or degrade predictably where safe.

### Efficiency
Every major pipeline stage should have measurable resource and latency behavior.

### Portability
Core domain logic must work on CPU-only hosts, constrained GPUs, workstation GPUs, and remote inference.

## 10. Product success metrics

Metrics are separated by layer:

Retrieval: MRR, Recall@K, Full Recall@K, candidate recall.

Legal understanding: issue/rule/exception/fact-to-rule accuracy.

Grounding: citation validity, claim support, unsupported-claim rate.

Safety: abstention precision/recall, conflict detection, temporal/jurisdiction correctness.

Operations: p50/p95 latency, CPU, RAM, VRAM, throughput, token use, cost, recovery success.

Business metrics are added after user validation: task completion time, repeat usage, workflow adoption, conversion, retention, and willingness to pay.

## 11. UX contract

The user must be able to distinguish:

- source law;
- system interpretation;
- evidence;
- uncertainty;
- missing evidence;
- conflicts.

The interface must not visually imply that generated prose is itself the legal authority.

## 12. Enterprise requirements later

- SSO and RBAC;
- tenant isolation;
- audit logs;
- data residency controls;
- private deployment;
- API quotas;
- configurable retention;
- source governance;
- knowledge-release management.

These are architectural targets, not first-stage implementation requirements.

## 13. Release principle

A product release is acceptable only when its quality profile is known. A feature may be released with limitations if those limitations are measured, documented, visible to the user, and do not violate safety/correctness invariants.
