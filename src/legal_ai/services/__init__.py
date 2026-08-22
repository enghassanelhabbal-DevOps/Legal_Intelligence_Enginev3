"""services sub-package — orchestration only (no business logic).

Public API:
    from src.legal_ai.services import QueryService
"""

from src.legal_ai.services.query_service import QueryService

__all__ = ["QueryService"]
