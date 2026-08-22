"""pipeline.py — Pipeline assembly helpers: build_index, prepare_pipeline.

Extracted from legal_rag_engine.py.  These functions wire together all
retrieval components and handle caching / knowledge versioning.
"""

from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from src.legal_ai.core.logging import get_logger
from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
from src.legal_ai.ingestion.normalization import tokenize
from src.legal_ai.knowledge import EmbeddingCache, KnowledgeVersion
from src.legal_ai.retrieval.bm25 import BM25
from src.legal_ai.retrieval.dense import DenseEncoder, DenseIndex
from src.legal_ai.retrieval.hybrid import HybridRetriever, _lexical_text, _metadata_text

LOGGER = get_logger(__name__)

DENSE_MODEL_NAME = "BAAI/bge-m3"
RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------

def configure_runtime(cfg: RuntimeConfig) -> str:
    """Configure torch settings and return the resolved device string."""
    import os
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    if cfg.num_threads > 0:
        torch.set_num_threads(cfg.num_threads)

    if cfg.enable_tf32 and torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    if cfg.device == "cpu":
        device = "cpu"
    elif cfg.device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but no CUDA GPU found.")
        device = f"cuda:{cfg.gpu_id}"
    else:
        device = f"cuda:{cfg.gpu_id}" if torch.cuda.is_available() else "cpu"

    LOGGER.info("Device: %s", device)
    if device.startswith("cuda"):
        LOGGER.info("GPU: %s", torch.cuda.get_device_name(cfg.gpu_id))
    return device


def choose_dtype(cfg: RuntimeConfig, device: str) -> torch.dtype:
    if not device.startswith("cuda"):
        return torch.float32
    if cfg.precision == "fp32":
        return torch.float32
    if cfg.precision == "bf16":
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16
        LOGGER.warning("BF16 not supported on this GPU; falling back to FP16.")
        return torch.float16
    if cfg.precision == "fp16":
        return torch.float16
    # auto
    return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16


# ---------------------------------------------------------------------------
# Index build (with embedding cache)
# ---------------------------------------------------------------------------

def build_index(
    documents: list[dict[str, Any]],
    encoder: DenseEncoder,
    bm25: BM25,
    batch_size: int,
    out_dir: Path,
) -> DenseIndex:
    """Build or load the FAISS index, using the embedding cache for speed.

    Writes into the canonical ARCHITECTURE_CONTRACT subdirectories:
      <out_dir>/embeddings/  — dense_embeddings.npy, embeddings_cache.json
      <out_dir>/indexes/     — dense_faiss.index
    """
    embeddings_dir = out_dir / "embeddings"
    indexes_dir = out_dir / "indexes"
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)

    embeddings_path = embeddings_dir / "dense_embeddings.npy"
    index_path = indexes_dir / "dense_faiss.index"
    cache_path = embeddings_dir / "embeddings_cache.json"
    cache = EmbeddingCache(cache_path)

    if embeddings_path.exists() and index_path.exists():
        LOGGER.info("Loading cached dense embeddings and FAISS index.")
        embeddings = np.load(embeddings_path, mmap_mode="r")
        index = DenseIndex.load(index_path)
        if index.index.ntotal != len(documents):
            raise ValueError("Cached index size does not match current document count.")
        return index

    texts = [_metadata_text(d) for d in documents]
    doc_hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]

    # Pre-fill from cache
    embeddings_list: list[np.ndarray | None] = [None] * len(documents)
    to_encode_indices: list[int] = []
    to_encode_texts: list[str] = []
    for i, h in enumerate(doc_hashes):
        cached = cache.get(h)
        if cached is not None:
            embeddings_list[i] = np.asarray(cached, dtype=np.float32)
        else:
            to_encode_indices.append(i)
            to_encode_texts.append(texts[i])

    if to_encode_texts:
        LOGGER.info("Encoding %d new embeddings (batch_size=%d)", len(to_encode_texts), batch_size)
        computed = encoder.encode_documents(to_encode_texts, batch_size=batch_size)
        for idx, emb in zip(to_encode_indices, computed):
            arr = np.asarray(emb, dtype=np.float32)
            embeddings_list[idx] = arr
            cache.set(doc_hashes[idx], emb.tolist())
        cache.persist()

    embeddings = np.vstack(embeddings_list).astype(np.float32)
    index = DenseIndex(embeddings)
    np.save(embeddings_path, embeddings)
    index.save(index_path)
    return index


# ---------------------------------------------------------------------------
# Full pipeline factory
# ---------------------------------------------------------------------------

def prepare_pipeline(
    documents: list[dict[str, Any]],
    runtime: RuntimeConfig,
    pipeline_cfg: PipelineConfig,
    out_dir: Path,
    load_reranker: bool = True,
) -> tuple[HybridRetriever, dict[str, Any]]:
    """Assemble and return (HybridRetriever, runtime_info_dict).

    Artifact layout (ARCHITECTURE_CONTRACT):
      <out_dir>/embeddings/  — dense_embeddings.npy, embeddings_cache.json
      <out_dir>/indexes/     — dense_faiss.index
      <out_dir>/reports/     — runtime_info.json
      <out_dir>/             — knowledge_version.json  (root, for version discovery)
    """
    reports_dir = out_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    device = configure_runtime(runtime)
    dtype = choose_dtype(runtime, device)
    LOGGER.info("Inference dtype: %s", dtype)

    encoder = DenseEncoder(DENSE_MODEL_NAME, device, dtype, runtime.max_seq_length)
    bm25 = BM25([tokenize(_lexical_text(d)) for d in documents])
    index = build_index(documents, encoder, bm25, runtime.dense_batch_size, out_dir)

    reranker = None
    if load_reranker:
        # Import lazily so that retrieval does not hard-depend on reranking
        from src.legal_ai.reranking import Reranker  # noqa: PLC0415
        reranker = Reranker(RERANKER_MODEL_NAME, device, dtype, runtime.max_seq_length)

    retriever = HybridRetriever(documents, encoder, index, bm25, reranker, pipeline_cfg)

    info: dict[str, Any] = {
        "device": device,
        "dtype": str(dtype),
        "gpu_name": torch.cuda.get_device_name(runtime.gpu_id) if device.startswith("cuda") else None,
        "cuda_version": torch.version.cuda,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "faiss": getattr(__import__("faiss"), "__version__", "unknown"),
    }
    _save_json(info, reports_dir / "runtime_info.json")

    # Save knowledge version manifest in root of out_dir for easy discovery
    try:
        h = hashlib.sha256()
        for d in documents:
            h.update(str(d.get("id")).encode())
            h.update(str(d.get("content", "")).encode())
        kv = KnowledgeVersion(
            version_id=f"v{int(time.time())}",
            dataset_hash=h.hexdigest(),
            document_count=len(documents),
            embedding_model=DENSE_MODEL_NAME,
            index_type="faiss-flat-ip",
        )
        kv.save(out_dir / "knowledge_version.json")
    except Exception as exc:
        LOGGER.warning("Could not write knowledge version manifest: %s", exc)

    return retriever, info


def _save_json(obj: Any, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


__all__ = ["build_index", "prepare_pipeline", "configure_runtime", "choose_dtype"]
