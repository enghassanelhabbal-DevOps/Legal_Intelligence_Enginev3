"""bm25.py — Pure-Python BM25 implementation (CPU).

Extracted from legal_rag_engine.py.
BM25 runs on CPU always — no GPU dependency (ARCHITECTURE_CONTRACT.md §Hardware).
"""

from __future__ import annotations

import math

import numpy as np

from src.legal_ai.ingestion.normalization import tokenize


class BM25:
    """Okapi BM25 retriever.

    Parameters
    ----------
    corpus_tokens:
        Pre-tokenised corpus. Each element is a list of tokens for one document.
    k1:
        Term frequency saturation parameter (default 1.5).
    b:
        Document length normalisation (default 0.75).
    """

    def __init__(
        self,
        corpus_tokens: list[list[str]],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = float(k1)
        self.b = float(b)
        self.corpus_size = len(corpus_tokens)
        self.doc_len = np.asarray([len(x) for x in corpus_tokens], dtype=np.float32)
        self.avgdl = float(np.mean(self.doc_len)) if self.corpus_size else 0.0

        self.doc_freqs: list[dict] = []
        df: dict = {}
        for tokens in corpus_tokens:
            freqs: dict = {}
            for token in tokens:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)
            for token in freqs:
                df[token] = df.get(token, 0) + 1

        self.idf = {
            term: math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def top_n(self, query: str, n: int) -> list[tuple[int, float]]:
        """Return top-n (doc_index, score) pairs sorted by descending score."""
        scores = np.zeros(self.corpus_size, dtype=np.float32)
        qtf: dict = {}
        for token in tokenize(query):
            qtf[token] = qtf.get(token, 0) + 1

        if not qtf or self.corpus_size == 0 or self.avgdl == 0:
            return []

        for term in qtf:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(term, 0)
                if not tf:
                    continue
                denom = tf + self.k1 * (
                    1.0 - self.b + self.b * self.doc_len[i] / self.avgdl
                )
                scores[i] += idf * (tf * (self.k1 + 1.0) / denom)

        n = min(max(1, n), len(scores))
        idx = np.argpartition(-scores, n - 1)[:n]
        idx = idx[np.argsort(-scores[idx], kind="stable")]
        return [(int(i), float(scores[i])) for i in idx]


__all__ = ["BM25"]
