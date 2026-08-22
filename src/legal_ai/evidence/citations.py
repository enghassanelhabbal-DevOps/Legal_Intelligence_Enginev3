"""citations.py — Citation validation utilities.

Checks that every claim in an LLM answer can be traced back to a source
in the provided evidence list.  This is the citation validation step
described in ARCHITECTURE_CONTRACT.md §Contracts (Answer.citations).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def validate_citations(
    citations: Sequence[dict[str, Any]],
    evidence: Sequence[dict[str, Any]],
) -> list[str]:
    """Validate that every cited source_id appears in the evidence.

    Returns a list of warning strings for any citation that cannot be
    traced back to a provided evidence item.

    Args:
        citations: List of citation dicts from the LLM response,
                   each expected to have an 'id' or 'source_id' key.
        evidence:  List of evidence dicts used as LLM context,
                   each expected to have an 'id' key.

    Returns:
        List of warning strings (empty if all citations are valid).
    """
    evidence_ids = {str(e.get("id", "")) for e in evidence}
    warnings: list[str] = []
    for c in citations:
        cid = str(c.get("id") or c.get("source_id") or "")
        if cid and cid not in evidence_ids:
            warnings.append(
                f"Citation id={cid!r} not found in evidence — possible hallucination."
            )
    return warnings


__all__ = ["validate_citations"]
