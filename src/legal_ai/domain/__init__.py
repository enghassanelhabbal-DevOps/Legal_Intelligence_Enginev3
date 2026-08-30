"""domain — canonical legal-resource identity, classification, and
provenance contracts. Introduced per docs/research/CORPUS_ARCHITECTURE_DIRECTION.md:
the long-term abstraction is `LegalResource` (legislative + judicial),
distinct from the retrieval-facing `LegalDocument`/chunk representation.

This package holds data contracts only — no retrieval, no I/O, no LLM
calls, per ARCHITECTURE_CONTRACT.md's layering rules.
"""
