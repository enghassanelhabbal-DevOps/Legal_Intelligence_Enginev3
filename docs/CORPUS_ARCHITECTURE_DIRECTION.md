# Corpus Architecture Direction — Egyptian Legal Intelligence

## Status
Approved direction for Stage 1 planning; implementation follows measurement and dataset audit.

## Why the direction changed

The full Dataflare corpus audit established that the corpus is predominantly jurisprudential/case-law material rather than statutes alone. Therefore the platform must not be designed as a statute-only Arabic RAG system.

The canonical product direction is:

> **Egyptian Legal Intelligence over legislation and jurisprudence, with evidence-first retrieval and explicit authority, jurisdiction, and temporal semantics.**

## Corpus roles

### Legislative corpus

Represents constitution, laws, regulations, normative instruments, and their versions where authoritative metadata is available.

Canonical hierarchy:

```text
LegalInstrument
  └─ LegalVersion
      └─ Part / Book
          └─ Chapter / Section
              └─ Article
                  └─ Paragraph / Clause
                      └─ Evidence Span
```

### Jurisprudential corpus

Represents judicial decisions and legally meaningful derived metadata.

Canonical hierarchy:

```text
JudicialDecision
  ├─ court
  ├─ chamber
  ├─ case / appeal identifier
  ├─ decision date
  ├─ publication/reference metadata
  ├─ cited authorities
  ├─ legal issue(s)
  ├─ legal principle(s), when reliably extractable
  └─ evidence spans
```

A legal principle extracted from a judgment must remain linked to the source judgment and must not be treated as legislation.

## Unified retrieval model

The system should eventually support authority-aware retrieval across both families:

```text
Query
  ↓
Query Understanding
  ↓
Jurisdiction / Date / Authority Constraints
  ↓
Legal Resource Retrieval
       ├─ Legislative retrieval
       └─ Jurisprudential retrieval
  ↓
Candidate Fusion / Ranking
  ↓
Evidence Set
  ↓
Claim ↔ Evidence validation
  ↓
Grounded reasoning
```

The ranking layer must not collapse different authority classes into one unexplained score. Authority type, temporal validity, jurisdiction, and source quality should remain inspectable signals.

## Dataflare role

The Dataflare corpus is accepted as a **candidate Egyptian legal knowledge source for Stage 1 ingestion and research**, subject to:

- provenance/license verification;
- record-level classification;
- duplicate removal/grouping;
- legal-structure extraction;
- source/citation extraction;
- overlap analysis against the existing 952-document corpus;
- quality and authority review.

It is not automatically accepted as a gold benchmark or as ground truth for legal validity.

## Existing 952 corpus role

The existing corpus remains useful as a separate baseline/reference corpus. Its role must be documented explicitly after overlap analysis rather than assumed.

## Important schema change

`LegalDocument` remains a compatibility/domain concept, but the long-term canonical abstraction is `LegalResource`, with explicit resource types such as:

- `LEGISLATIVE`
- `JUDICIAL`
- `REGULATORY`
- `CONSTITUTIONAL`
- `SECONDARY`
- `PRIVATE_USER`

The implementation should introduce this abstraction only when the current contracts can absorb it without unnecessary migration risk.

## Segmentation principle

Never make generic text chunks the primary legal truth.

Use:

```text
source document
→ detected legal structure
→ atomic legal unit
→ retrieval projection
```

Chunks are derived retrieval representations. They must retain stable references to their source unit.

## Evaluation consequence

Two benchmark families are required:

1. **Legislative retrieval/understanding** — articles, provisions, conditions, exceptions, versions.
2. **Jurisprudential retrieval/understanding** — judgments, citations, principles, issues, and application context.

A future end-to-end benchmark must also test mixed questions where legislation and case law are both necessary.

## Product consequence

The first product wedge remains Egyptian legal research + evidence reports, but the backend is explicitly dual-domain from this point forward:

```text
Statute / Regulation Intelligence
+
Case Law / Judicial Intelligence
=
Egyptian Legal Research Intelligence
```

This is an architectural expansion of the knowledge layer, not permission to expand the first UX into many workflows simultaneously.

## Research hypotheses

- Hierarchical legal retrieval will reduce candidate count while preserving recall.
- Authority-aware ranking will improve evidence quality versus flat semantic ranking.
- Citation-grounded jurisprudence retrieval will improve verifiability.
- Article/provision-aware representations will outperform arbitrary chunking for statute retrieval.
- Evidence-span grounding will improve claim support without requiring a larger generator.
- Resource-aware candidate pruning can reduce reranker cost while preserving multi-evidence recall.

All hypotheses require reproducible experiments.
