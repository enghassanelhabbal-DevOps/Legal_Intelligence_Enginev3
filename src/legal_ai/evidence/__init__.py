"""evidence sub-package — evidence selection, context building, citation validation.

Public API:
    from src.legal_ai.evidence import build_grounded_context
    from src.legal_ai.evidence import select_evidence, validate_citations
"""

from src.legal_ai.evidence.builder import build_grounded_context, select_evidence
from src.legal_ai.evidence.citations import validate_citations

__all__ = ["build_grounded_context", "select_evidence", "validate_citations"]
