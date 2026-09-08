# Single canonical Dockerfile — used by BOTH the api and streamlit services in
# docker-compose.yml (via different `command:` overrides). Replaces the two
# conflicting Dockerfiles that previously existed (root: python:3.12-slim +
# pyproject.toml; api/: python:3.10-slim + a separate api/requirements.txt).
#
# Python version MUST match pyproject.toml's `requires-python = ">=3.12"`.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system deps needed by faiss/torch wheels at runtime (kept minimal —
# CPU wheels are used by default; see pyproject.toml [project.optional-dependencies].gpu
# for a CUDA image variant).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
COPY api/ ./api/
COPY ui/ ./ui/
COPY scripts/ ./scripts/
COPY configs/ ./configs/

# Which pyproject.toml extras to install — see [project.optional-dependencies].
# Defaults to "dense" because the default CMD below runs the API, and the
# API's default ExecutionProfile (BALANCED/ACCELERATED, resolved from
# discovered hardware unless EXECUTION_PROFILE overrides it — see
# api/app.py) uses local dense retrieval/reranking, which requires torch/
# faiss-cpu/sentence-transformers. Building a lightweight/remote-generation-
# only image (no dense retrieval, no torch/faiss at all — see DR-030) is a
# deliberate, explicit choice at build time, not an accident of a bare
# `pip install -e .`:
#   docker build --build-arg INSTALL_EXTRAS= .                (lightweight)
#   docker build --build-arg INSTALL_EXTRAS=dense .           (default)
#   docker build --build-arg INSTALL_EXTRAS=dense,qwen .      (local Qwen)
#   docker build --build-arg INSTALL_EXTRAS=streamlit .       (UI-only image)
# See DR-037.
ARG INSTALL_EXTRAS=dense

RUN python -m pip install --upgrade pip setuptools wheel && \
    if [ -n "$INSTALL_EXTRAS" ]; then \
        python -m pip install -e ".[${INSTALL_EXTRAS}]"; \
    else \
        python -m pip install -e "."; \
    fi

# legal_documents.json and artifacts/ are mounted as volumes in
# docker-compose.yml rather than baked into the image, so re-indexing a
# corpus update never requires a rebuild.

EXPOSE 8000 8501

# Default command runs the API; docker-compose.yml overrides this for the
# streamlit service. Kept as a sane default for `docker run` without compose.
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
