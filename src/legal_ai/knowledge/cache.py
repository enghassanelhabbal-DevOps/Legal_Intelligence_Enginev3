"""cache.py — Embedding cache implementations.

Migrated from legal_ai/knowledge.py (EmbeddingCacheJSON, EmbeddingCacheLMDB, EmbeddingCache).
"""

from __future__ import annotations

import json
from pathlib import Path


class EmbeddingCacheJSON:
    """JSON-backed embedding cache keyed by document hash.

    Suitable for development and small datasets (< ~50k documents).
    For production scale use EmbeddingCacheLMDB.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, list[float]] = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def get(self, doc_hash: str) -> list[float] | None:
        return self._data.get(doc_hash)

    def set(self, doc_hash: str, embedding: list[float]) -> None:
        self._data[doc_hash] = embedding

    def persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False), encoding="utf-8"
        )

    def close(self) -> None:
        pass


class EmbeddingCacheLMDB:
    """LMDB-backed embedding cache — better performance on large datasets.

    Falls back to EmbeddingCacheJSON if the *lmdb* package is unavailable.
    """

    def __init__(self, path: Path, map_size: int = 1 << 30) -> None:
        import lmdb  # type: ignore

        self.path = path
        self._env = lmdb.open(str(path), map_size=map_size, subdir=False, lock=True)

    def get(self, doc_hash: str) -> list[float] | None:
        with self._env.begin() as txn:
            v = txn.get(doc_hash.encode("utf-8"))
            if v is None:
                return None
            return json.loads(v.decode("utf-8"))

    def set(self, doc_hash: str, embedding: list[float]) -> None:
        with self._env.begin(write=True) as txn:
            txn.put(
                doc_hash.encode("utf-8"),
                json.dumps(embedding, ensure_ascii=False).encode("utf-8"),
            )

    def persist(self) -> None:
        # LMDB commits on put; nothing extra needed
        pass

    def close(self) -> None:
        try:
            self._env.close()
        except Exception:
            pass


class EmbeddingCache:
    """Factory — selects LMDB if available, otherwise falls back to JSON cache."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            import lmdb  # noqa: F401  # type: ignore

            path.parent.mkdir(parents=True, exist_ok=True)
            lmdb_path = path.with_suffix("").with_name(path.name + ".lmdb")
            self._impl: EmbeddingCacheJSON | EmbeddingCacheLMDB = EmbeddingCacheLMDB(lmdb_path)
        except Exception:
            self._impl = EmbeddingCacheJSON(path)

    def get(self, doc_hash: str) -> list[float] | None:
        return self._impl.get(doc_hash)

    def set(self, doc_hash: str, embedding: list[float]) -> None:
        self._impl.set(doc_hash, embedding)

    def persist(self) -> None:
        self._impl.persist()

    def close(self) -> None:
        if hasattr(self._impl, "close"):
            try:
                self._impl.close()
            except Exception:
                pass


__all__ = ["EmbeddingCacheJSON", "EmbeddingCacheLMDB", "EmbeddingCache"]
