"""retrieval sub-package — BGE-M3 dense retrieval, FAISS, BM25, candidate fusion.

Public API:
    from src.legal_ai.retrieval import DenseEncoder, DenseIndex, BM25
    from src.legal_ai.retrieval import HybridRetriever
    from src.legal_ai.retrieval import build_index, prepare_pipeline

Import strategy
----------------
`BM25` is pure NumPy and always importable. `DenseEncoder` / `DenseIndex` /
`HybridRetriever` / `build_index` / `prepare_pipeline` depend on torch/faiss,
which are heavy, sometimes GPU-driver-sensitive dependencies that are not
needed for BM25-only contexts (e.g. the fast CI regression gate, or a
Streamlit-only deployment that never runs local retrieval). Those symbols are
loaded lazily on first access via module `__getattr__` (PEP 562) so importing
this package never requires torch/faiss unless one of those names is actually
used — while `from src.legal_ai.retrieval import DenseIndex` still works
exactly as before when the heavy deps ARE installed.
"""

from __future__ import annotations

from typing import Any

from src.legal_ai.retrieval.bm25 import BM25

__all__ = [
    "DenseEncoder",
    "DenseIndex",
    "BM25",
    "HybridRetriever",
    "build_index",
    "prepare_pipeline",
]

_LAZY = {
    "DenseEncoder": ("src.legal_ai.retrieval.dense", "DenseEncoder"),
    "DenseIndex": ("src.legal_ai.retrieval.dense", "DenseIndex"),
    "HybridRetriever": ("src.legal_ai.retrieval.hybrid", "HybridRetriever"),
    "build_index": ("src.legal_ai.retrieval.pipeline", "build_index"),
    "prepare_pipeline": ("src.legal_ai.retrieval.pipeline", "prepare_pipeline"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module_name, attr_name = _LAZY[name]
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:  # pragma: no cover - depends on optional deps
            raise ImportError(
                f"'{name}' requires torch/faiss (dense retrieval extras). "
                f"Install with: pip install -e '.[qwen]' or ensure faiss-cpu/torch "
                f"are installed. Original error: {exc}"
            ) from exc
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
