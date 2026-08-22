# Legal Intelligence Engine

Arabic legal retrieval + grounded generation over the Egyptian legal corpus (Penal
Code, Criminal Procedures Code, and related laws). Follows the architecture
contract in `ARCHITECTURE_CONTRACT.md`.

## What is actually included (verified working, not aspirational)

- Retrieval: BM25 (`src/legal_ai/retrieval/bm25.py`, pure NumPy) + dense
  (BGE-M3/FAISS, optional — see extras below) + reranking.
- One canonical Streamlit UI (`ui/streamlit_app.py`) that runs in **remote
  mode** against a hosted API, or **embedded mode** (calls `QueryService`
  in-process) when no API is deployed — same retrieval/generation code either
  way, never duplicated in the UI.
- One canonical FastAPI service (`api/app.py`) with a proper startup
  lifecycle (`QueryService`/`LLMManager` built once, not per-request),
  a `/v1/ready` probe distinct from `/v1/health`, and schema-validated
  ingestion.
- LLM generation behind an adapter (`src/legal_ai/generation/manager.py`):
  local Qwen3 (Transformers) or any OpenAI-compatible remote endpoint
  (OpenAI, Gemini, Ollama, vLLM, ...), selected by config — swapping the
  backend never touches the retrieval engine.
- A **real** retrieval regression gate (`scripts/regression_harness.py` +
  `scripts/quality_gate.py`) that runs the actual BM25 engine against the
  actual 952-article corpus and a reproducible evaluation set
  (`scripts/build_eval_set.py`) — not a synthetic 3-sentence fixture.
- DVC-tracked large artifacts (embeddings, FAISS index) — `git ls-files`
  contains only `.dvc` pointer files, not the binaries themselves.
- Docker + Docker Compose (one Dockerfile, two services) and a GitHub
  Actions CI workflow that actually runs lint, tests, the regression gate,
  and a Docker build on every PR.

## Running the Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

This is the **only** documented Streamlit entry point. Set `LEGAL_API_URL`
(env var or Streamlit secret) to run against a separately hosted API, or
leave it unset to run in embedded mode (needs the full retrieval stack —
see `requirements.txt`).

## Quick start (local development)

```bash
python -m venv .venv
. .venv/bin/activate  # PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"          # add ".[qwen]" for local Qwen3, ".[gpu]" for CUDA FAISS

pytest                                      # fast tier, no heavy ML deps required
python scripts/build_eval_set.py            # build the real evaluation set (once)
python scripts/regression_harness.py        # measure real retrieval quality
python scripts/quality_gate.py              # fail if it regressed
```

## Docker

```bash
docker compose up --build
```

API on `http://localhost:8000`, UI on `http://localhost:8501` (talks to the
API automatically via `LEGAL_API_URL=http://api:8000/v1/query`).

## DVC (large artifacts)

```bash
dvc pull     # fetch embeddings/index from the configured remote
# after regenerating embeddings/index:
dvc add artifacts/embeddings/dense_embeddings.npy artifacts/indexes/dense_faiss.index
dvc push
```

Set a real remote before relying on this in CI/teammates:
`dvc remote add -d prod gs://your-bucket/legal-rag-artifacts` (or s3://).

## Cross-platform notes

Runs on Windows, WSL2, Ubuntu, and Docker from one codebase — no OS-specific
forks. `faiss-cpu` is the default (see `pyproject.toml`'s `gpu` extra for
CUDA). Local Qwen3 inference requires the `qwen` extra and is optional; the
system is fully functional with an OpenAI-compatible remote backend alone.
See `docs/WSL_TESTING.md` and `INSTALL_GPU.md` for hardware-specific notes.
