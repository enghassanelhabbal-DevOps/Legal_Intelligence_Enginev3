# Portability and Runtime Profiles

The Legal Intelligence Engine must run from one codebase across Windows, WSL2, Linux, CPU-only systems, constrained GPUs, modern GPUs, and remote inference backends.

## Supported runtime intent

- Windows 10/11
- WSL2
- Ubuntu/Linux
- Docker
- CPU-only development
- constrained GPU development
- modern GPU acceleration
- remote LLM endpoints

No OS-specific fork is allowed for domain/retrieval logic.

## Execution profiles

Use runtime profiles rather than machine-specific code branches:

- `cpu-minimal`: CPU-first retrieval and remote or lightweight generation
- `balanced`: bounded local retrieval/reranking with conservative memory use
- `accelerated`: measured GPU acceleration where justified
- `remote-llm`: local retrieval/evidence with an approved remote generation provider

The Quadro M2200 4 GB environment is a stress/compatibility target. It must not constrain the platform architecture or justify unsafe assumptions such as FP8/Tensor Core availability.

## Resource rules

- Bound workers, queues, and batch sizes.
- Avoid predictable model co-residency OOM.
- Keep FAISS/BM25 CPU-first where appropriate.
- Do not download models at request time.
- Prefer unload/offload/degraded-mode behavior over process failure.
- Measure before claiming a performance improvement.

## Canonical entry points

- API: `api/app.py`
- Streamlit UI: `ui/streamlit_app.py`
- Package/domain code: `src/legal_ai/`

Do not revive removed legacy scripts or create hardware-specific copies of the engine.

## Installation

Use `pyproject.toml` extras instead of standalone machine-specific requirements files where possible.

```bash
python -m venv .venv
# activate the environment for your OS
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Optional local-model/GPU support:

```bash
python -m pip install -e ".[qwen,gpu]"
```

Install a CUDA-enabled PyTorch build appropriate for the target driver/OS before relying on GPU execution. See `docs/runbooks/GPU_SETUP.md`.

## Verification

Every supported environment should eventually exercise the same contracts with environment-appropriate dependencies. Environment-specific test exclusions must be explicit; do not call a run a full suite when optional dependency tests were not executed.
