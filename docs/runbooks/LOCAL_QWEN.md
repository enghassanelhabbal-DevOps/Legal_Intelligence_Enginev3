Local Qwen Runbook (developer guide)

This document explains how to prepare a dedicated Linux host or container to run the Local Qwen + FAISS stack safely for development/testing. DO NOT run this on Streamlit Cloud.

1) Host preparation (Ubuntu 22.04)
- Update & install required packages:
  sudo apt-get update && sudo apt-get install -y build-essential git wget curl python3-dev python3-venv libsndfile1

2) Python environment
- Create a venv and activate it:
  python3 -m venv .venv
  source .venv/bin/activate
- Upgrade pip and install requirements (create requirements-local.txt with needed libs):
  pip install -U pip
  pip install -r requirements-local.txt

3) Native deps and FAISS
- For CPU-only FAISS:
  pip install faiss-cpu
- For GPU FAISS (requires NVIDIA libs) see FAISS docs.

4) Model files
- Use HF or local model storage. Ensure enough disk space (tens of GB). Store models under /opt/models or ./artifacts/models

5) Running backend
- Use the api service in this repo as the inference wrapper (implements /query endpoint)
- Set ALLOW_LOCAL_MODEL_RUNTIME=1 when you start the backend in this environment only

6) Docker
- Optionally build the Docker image from api/Dockerfile and run with appropriate mounts and GPU flags for GPU hosts

7) Safety
- Set firewall rules and only expose port 8000 to internal networks or via a secure reverse proxy

8) Troubleshooting
- If native extension compile fails, ensure build-essential and python-dev are present and check pip logs
- Check memory usage: local models can consume tens of GB of RAM

End of Local Qwen Runbook.