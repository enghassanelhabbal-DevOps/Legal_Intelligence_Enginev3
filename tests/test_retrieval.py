from __future__ import annotations

import unittest
import numpy as np
from src.legal_ai.retrieval import BM25, DenseIndex, HybridRetriever
from src.legal_ai.core.models import RetrievalHit


class TestRetrievalComponents(unittest.TestCase):
    def test_bm25_basic(self):
        corpus = [["قانون", "المادة", "عقوبات"], ["مدني", "عقد", "التزام"], ["جنائي", "جريمة", "قانون"]]
        bm25 = BM25(corpus)
        top = bm25.top_n("قانون", 2)
        # ensure indices returned and score for first > second (if multiple)
        self.assertTrue(len(top) >= 1)
        idx, score = top[0]
        self.assertIn(idx, {0, 2})
        self.assertGreaterEqual(score, 0)

    def test_denseindex_search(self):
        # create simple 3-d embeddings
        emb = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
        idx = DenseIndex(emb)
        q = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        scores, indices = idx.search(q, 1)
        self.assertEqual(indices.shape[1], 1)
        self.assertEqual(int(indices[0, 0]), 0)

    def test_dense_preserving_union(self):
        # Prepare dummy RetrievalHit objects using real fields from core.models
        d1 = RetrievalHit(document_id="1", index=0, text="A", law_name="قانون", article_id="1", dense_score=0.9)
        d2 = RetrievalHit(document_id="2", index=1, text="B", law_name="قانون", article_id="2", dense_score=0.8)
        b1 = RetrievalHit(document_id="2", index=1, text="B", law_name="قانون", article_id="2", bm25_score=1.0)
        b2 = RetrievalHit(document_id="3", index=2, text="C", law_name="قانون", article_id="3", bm25_score=0.5)
        merged = HybridRetriever.dense_preserving_union([d1, d2], [b1, b2], max_candidates=10)
        # dense items should be first in order
        self.assertGreaterEqual(len(merged), 3)
        self.assertEqual(merged[0].document_id, "1")
        self.assertEqual(merged[1].document_id, "2")
        # unique bm25 item appended after dense
        ids = [h.document_id for h in merged]
        self.assertIn("3", ids)


if __name__ == "__main__":
    unittest.main()
