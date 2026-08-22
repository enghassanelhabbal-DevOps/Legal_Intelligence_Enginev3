from __future__ import annotations

import unittest
from src.legal_ai.ingestion import article_aware_chunk, chunk_document


class TestIngestionChunking(unittest.TestCase):
    def test_article_chunking_basic(self):
        text = "المادة 1 هذا نص المادة الأولى.\nالمادة 2 هذا نص المادة الثانية."
        chunks = article_aware_chunk(text, max_chars=1000)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["article_id"], "1")
        self.assertIn("المادة 1", chunks[0]["text"])

    def test_large_article_split(self):
        # create a single long article
        long_body = "المادة 10 " + ("كلمة " * 1000)
        chunks = article_aware_chunk(long_body, max_chars=200)
        self.assertTrue(len(chunks) > 1)
        for c in chunks:
            self.assertEqual(c["article_id"], "10")

    def test_chunk_document_provenance(self):
        doc = {"document_id": "doc1", "raw_text": "المادة 1 نص.", "metadata": {"title": "قانون"}}
        out = chunk_document(doc, max_chars=1000)
        self.assertEqual(out[0]["document_id"], "doc1")
        self.assertEqual(out[0]["article_id"], "1")


if __name__ == "__main__":
    unittest.main()
