"""logging.py — Centralised logger factory.

Usage:
    from src.legal_ai.core.logging import get_logger
    logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
import os

_FMT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(format=_FMT, datefmt=_DATE_FMT, level=level)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger named *name* (pass ``__name__`` from the calling module)."""
    _configure_root()
    return logging.getLogger(name)


__all__ = ["get_logger"]
