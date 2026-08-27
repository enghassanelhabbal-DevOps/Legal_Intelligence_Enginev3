# Legal Domain Specification

## Purpose

Define the legal semantics the engine must preserve so that retrieval, reasoning, evidence, and generation operate on legal meaning rather than plain text similarity.

## 1. Jurisdiction

Every legal knowledge item MUST carry an explicit jurisdiction. Minimum target values are controlled identifiers such as `EG`, `SA`, `AE`, `QA`, and future jurisdiction packs.

Rules:
- A query with an explicit jurisdiction must not silently retrieve another jurisdiction.
- Cross-jurisdiction comparison is an explicit mode.
- Similar wording is not equivalence.
- Missing jurisdiction is a data-quality condition, not permission to guess.

## 2. Legal authority

Authority is an explicit property:

```text
PRIMARY_OFFICIAL
JUDICIAL_OFFICIAL
REGULATORY_OFFICIAL
SECONDARY_REPUTABLE
PRIVATE_USER
UNKNOWN
```

Authority should influence retrieval and presentation but must not be invented from text.

## 3. Legal time

A legal rule can have multiple dates:

- publication date;
- effective-from date;
- effective-to date;
- amendment date;
- repeal date;
- supersession date.

A `version_id` identifies the legal representation valid for a defined interval.

### Query semantics

The engine should support:

```text
current law
law as of YYYY-MM-DD
law before amendment X
law after amendment X
historical version lookup
```

If the date is unknown but materially changes the answer, the system should warn or request clarification rather than silently assume current law.

## 4. Legal structure

Preserve hierarchy:

```text
Law
 └─ Book/Part
    └─ Chapter
       └─ Section
          └─ Article
             └─ Paragraph/Clause
```

An article identifier must remain linked to its parent law and version.

## 5. Amendments and relationships

The knowledge layer should represent:

```text
AMENDS
REPEALS
SUPERSEDES
SUPERSEDED_BY
RESTORES
REFERENCES
IMPLEMENTS
RELATED_TO
```

Relationships require provenance. Do not infer a legal relationship from semantic similarity alone when authoritative metadata is absent.

## 6. Legal citation

Canonical citation should include enough information to reproduce the authority:

```text
jurisdiction
law name / identifier
version/as-of context when applicable
article/paragraph
source reference
page/section when relevant
```

User-facing citations should prefer precise article-level references when the source supports them.

## 7. Legal question taxonomy

Minimum query classes:

- direct article lookup;
- rule explanation;
- definition/term question;
- condition question;
- exception question;
- prohibition/duty question;
- penalty/sanction question;
- procedural question;
- fact-to-rule application;
- multi-article synthesis;
- temporal/historical question;
- jurisdiction comparison;
- conflict/contradiction question;
- evidence sufficiency question;
- unanswerable/out-of-scope question.

## 8. Legal reasoning representation

The system should internally represent a legal answer as:

```text
Issue
Facts relevant to issue
Applicable rule(s)
Conditions
Exceptions
Application
Conclusion
Evidence
Uncertainty
```

Not every query needs every field. The representation is a reasoning scaffold, not a requirement to expose chain-of-thought.

## 9. Evidence roles

An evidence item can have one or more roles:

```text
RULE
DEFINITION
CONDITION
EXCEPTION
PROCEDURE
PENALTY
FACTUAL_PREMISE
COUNTER_AUTHORITY
CONTEXT
```

Roles may be predicted by the system but should be benchmarked before they are treated as authoritative metadata.

## 10. Conflict semantics

Potential conflict states:

- no conflict detected;
- direct textual conflict candidate;
- version conflict;
- jurisdiction conflict;
- authority disagreement;
- incomplete evidence.

A conflict candidate is not automatically a true legal contradiction. It must be surfaced with provenance and, where possible, resolved through higher-authority or newer applicable sources.

## 11. Legal ambiguity

The engine should distinguish:

- linguistic ambiguity;
- missing fact;
- missing jurisdiction;
- missing date;
- competing authorities;
- incomplete corpus;
- uncertain interpretation.

Ambiguity must not be hidden by confident prose.

## 12. Answer policy

A final answer should conceptually distinguish:

1. **Source-backed legal material** — what the retrieved authority states.
2. **System interpretation** — how the evidence answers the user's question.
3. **Uncertainty** — what cannot be established confidently.
4. **Missing evidence** — what is not available in the knowledge base.

## 13. Egyptian law first

The first corpus and expert benchmark should focus on Egyptian law. Candidate initial domains include criminal law, criminal procedure, civil law, commercial law, labor, tax/regulatory domains as high-quality corpora become available.

Domain expansion requires:

- domain metadata;
- authoritative source mapping;
- domain-specific evaluation;
- terminology coverage;
- temporal coverage.

## 14. Arabic language policy

Preserve original Arabic legal text. Retrieval may use normalized representations, but user-facing citations should show source-faithful text.

Normalization must not change:
- article identity;
- numbers;
- dates;
- negation;
- legal exceptions;
- punctuation whose meaning is legally material.

## 15. Legal safety

The product is decision support, not automatic legal representation. Product language must avoid presenting generated interpretation as binding legal authority.

High-risk workflows should surface uncertainty and encourage professional review where appropriate.
