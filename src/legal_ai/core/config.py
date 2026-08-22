"""config.py — Configuration loaders.

Migrated from legal_ai/config.py with the following changes:
  - Imports updated to src.legal_ai.core.models
  - Config dataclass extended with all fields used by the pipeline
  - load_runtime_config now builds RuntimeConfig (not RuntimeConfigLite)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.legal_ai.core.models import RuntimeConfig


def set_seed(seed: int = 42) -> None:
    import random

    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(False)

def load_json(path: Path) -> Any:
    import json
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a flat string dict (no shell expansion)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip().strip('"')
    return env


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML config file.  Returns {} if PyYAML is not installed or file absent."""
    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Config dataclass (all configurable values in one place)
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """All configurable values for the Legal AI platform.

    Values are loaded from (highest precedence first):
      os.environ > .env file > YAML file > defaults below
    """

    # Runtime
    runtime_device: str = "auto"
    runtime_gpu_id: int = 0
    runtime_precision: str = "auto"
    dense_batch_size: int = 32
    rerank_batch_size: int = 32
    num_threads: int = 0
    enable_tf32: bool = True

    # Models
    dense_model_name: str = "BAAI/bge-m3"
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    llm_backend: str = "qwen_transformers"

    # Artifacts / paths
    faiss_index_path: str = "artifacts/indexes/dense_faiss.index"
    embeddings_cache_path: str = "artifacts/embeddings/embeddings_cache.json"
    data_raw_dir: str = "data/raw"
    data_normalized_dir: str = "data/normalized"

    # Pipeline
    dense_candidates: int = 30
    bm25_candidates: int = 10
    rerank_candidates: int = 40
    final_k: int = 5
    max_context_chars: int = 14_000

    # API
    api_rate_limit: int = 30
    api_key: str = ""


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_config(
    env_path: str | None = None,
    yaml_path: str | None = None,
) -> dict[str, Any]:
    """Load configuration from YAML, then .env file, then os.environ.

    Precedence (highest → lowest): os.environ > .env > yaml > defaults.
    """
    cfg: dict[str, Any] = {}
    if yaml_path:
        cfg.update(_load_yaml(Path(yaml_path)))
    if env_path:
        cfg.update(_parse_dotenv(Path(env_path)))
    # Runtime env vars always win
    cfg.update(os.environ)
    return cfg


def load_runtime_config(cfg_map: dict[str, Any] | None = None) -> RuntimeConfig:
    """Build a RuntimeConfig from a loaded config map (or os.environ + .env)."""
    m = cfg_map or load_config(env_path=".env")

    def _get(key_upper: str, key_lower: str, default):  # noqa: ANN001
        return m.get(key_upper, m.get(key_lower, default))

    return RuntimeConfig(
        device=_get("RUNTIME_DEVICE", "runtime_device", "auto"),
        gpu_id=int(_get("RUNTIME_GPU_ID", "runtime_gpu_id", 0)),
        precision=_get("RUNTIME_PRECISION", "runtime_precision", "auto"),
        dense_batch_size=int(_get("DENSE_BATCH_SIZE", "dense_batch_size", 32)),
        rerank_batch_size=int(_get("RERANK_BATCH_SIZE", "rerank_batch_size", 32)),
        num_threads=int(_get("NUM_THREADS", "num_threads", 0)),
        enable_tf32=str(_get("ENABLE_TF32", "enable_tf32", "true")).lower() != "false",
    )


if __name__ == "__main__":
    import json
    print(json.dumps(load_config(env_path=".env"), ensure_ascii=False, indent=2))


__all__ = ["Config", "load_config", "load_runtime_config", "set_seed", "load_json"]
