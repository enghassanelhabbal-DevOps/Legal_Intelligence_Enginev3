# Portable Legal RAG Engine — Windows 10/11 + Linux

## What changed
- GPU-aware PyTorch execution with automatic CUDA detection.
- FP16/BF16/FP32 selection.
- Batched BGE-M3 embedding inference.
- Batched BGE reranker inference.
- Optional torch.compile for reranker.
- FAISS CPU by default for Windows/Linux portability.
- Dense-preserving candidate union: BM25 cannot evict Dense candidates.
- LLM-ready `RAGService` and `LLMBackend` interface.
- Persistent FAISS + embeddings cache.
- Runtime and experiment metadata saved to JSON.

## Why FAISS CPU by default
For the current ~1k-document corpus, FAISS search is tiny compared with Transformer inference. GPU acceleration matters much more for BGE-M3, reranking, and later the LLM. FAISS GPU remains optional on Linux/Conda.

## Windows 10/11
1. Create a virtual environment with Python 3.10/3.11/3.12.
2. Install the CUDA-enabled PyTorch build from the official PyTorch selector.
3. Then install:
   pip install -r requirements-windows-gpu.txt

Verify:
   python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"

## Linux
1. Create a virtual environment with Python 3.10/3.11/3.12.
2. Install the CUDA-enabled PyTorch build from the official PyTorch selector.
3. Then install:
   pip install -r requirements-linux-gpu.txt

## Run
python legal_rag_engine.py --documents "legal_documents (1).json" --output artifacts_portable

For larger GPUs:
python legal_rag_engine.py --dense-batch-size 64 --rerank-batch-size 64

For low VRAM:
python legal_rag_engine.py --dense-batch-size 8 --rerank-batch-size 8 --precision fp16

Enable compilation after baseline performance is correct:
python legal_rag_engine.py --compile-reranker

## LLM integration
The core returns:
- ranked legal sources
- stable source IDs
- metadata
- retrieval latency
- grounded context

Then plug in an LLM through `LLMBackend` and `RAGService` without changing retrieval.
