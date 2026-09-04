"""reranking sub-package — cross-encoder scoring.

Public API:
    from src.legal_ai.reranking import Reranker

`Reranker` depends on torch/sentence-transformers (the `dense` extra) — the
same heavy, sometimes GPU-driver-sensitive dependencies as `retrieval`'s
dense-retrieval symbols. Loaded lazily on first access via module
`__getattr__` (PEP 562), matching src/legal_ai/retrieval/__init__.py's
pattern, so `import src.legal_ai.reranking` never requires torch unless
`Reranker` is actually used — relevant since CPU-minimal execution
profiles disable the reranker by policy (see runtime/budgets.py,
rerank_batch_size=0) and never touch this import at all.
"""

from __future__ import annotations

from typing import Any

__all__ = ["Reranker"]

_LAZY = {"Reranker": ("src.legal_ai.reranking.cross_encoder", "Reranker")}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module_name, attr_name = _LAZY[name]
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:  # pragma: no cover - depends on optional deps
            raise ImportError(
                f"'{name}' requires torch/sentence-transformers (the 'dense' extra). "
                f"Install with: pip install -e '.[dense]'. Original error: {exc}"
            ) from exc
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
