# Legal RAG + Qwen3 on NVIDIA Quadro M2200

## Hardware target

- Windows 10/11 or Linux
- NVIDIA Quadro M2200
- 4 GB VRAM
- Maxwell / SM 5.2

## Model policy

The application accepts the requested model ID:

`Qwen/Qwen3-4B-Thinking-2507-FP8`

but on the Quadro M2200 it automatically falls back to:

`Qwen/Qwen3-4B-Thinking-2507`

and uses Transformers + Accelerate CPU offload.

This is intentional: the M2200 is not a practical target for accelerated fine-grained FP8 inference, and its 4 GB VRAM cannot hold the 4B model in normal FP16 GPU residency.

## Important `return_dict=True`

The Qwen model card uses:

```python
inputs = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
)
```

We keep `return_dict=True` deliberately. It gives us a dict-like object containing model inputs such as `input_ids` and `attention_mask`, which can then be passed through:

```python
model.generate(**inputs)
```

## Install

1. Use Python 3.12.
2. Install a CUDA-enabled PyTorch wheel compatible with your NVIDIA driver.
3. Install:

```powershell
pip install -r requirements-qwen-m2200.txt
```

4. Verify:

```powershell
python check_gpu.py
```

## Run

Put these files beside your existing `legal_rag_engine.py`:

- `qwen_transformers_backend.py`
- `app_qwen_m2200.py`

Then:

```powershell
python app_qwen_m2200.py --query "ما شروط القبض على المتهم في حالة التلبس؟"
```

Recommended M2200 defaults:

- retrieval dense batch: 4
- reranker batch: 1
- dense max length: 384
- reranker max chars: 3500
- final sources to LLM: 5
- Qwen max new tokens: 320
- Qwen GPU memory budget: 3.2 GiB
- CPU memory budget: 12 GiB

## Performance policy

The application intentionally treats the GPU as a scarce resource.

1. Retrieval runs first.
2. Retrieval Transformer models are released from GPU memory.
3. Qwen is loaded with CPU offload.
4. Only the Qwen model is kept GPU-heavy during generation.

This prevents BGE + reranker + Qwen from competing for the same 4 GB VRAM.

## Legal safety

The LLM is grounded only on retrieved legal context. The prompt requires article/law citations when available and instructs the model not to invent unsupported legal provisions.

## Output

`artifacts_m2200/last_answer.json` contains:

- answer
- retrieved sources
- grounded context
- retrieval latency
- generation latency
- runtime information
- actual LLM selected by the hardware policy
