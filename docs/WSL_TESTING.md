Testing on WSL (Ubuntu) - End-to-end (Streamlit UI + Backend)

This guide explains how to use your local WSL Ubuntu environment to test the full stack: Streamlit UI + FastAPI backend + optional local model container. It's designed to mimic the production setup on a VM and helps catch environment-specific issues.

Prerequisites on Windows host:
- WSL 2 enabled with Ubuntu (you mentioned you have WSL)
- Install Docker Desktop and enable WSL integration, or install Docker inside WSL
- Ensure sufficient disk space and memory for local model testing

Steps
1. Open WSL terminal (Ubuntu)
2. Clone the repo and checkout the branch:
   git clone https://github.com/enghassanelhabbal-DevOps/legal_rag_engine.git
   cd legal_rag_engine
   git checkout agents/devops-mlops-streamlit-integration
3. Copy example env and edit values:
   cp .env.example .env
   # Edit .env: set API_KEY, HF_TOKEN, GEMINI_MODEL, OPENAI_API_KEY as needed
4. Start backend and optional model locally with docker-compose (example):
   docker compose -f docker-compose.example.yml up -d --build
   # Wait for containers to be healthy. Check logs with docker compose logs -f api
5. Run Streamlit UI locally in WSL or Windows (prefer WSL):
   # set env vars in WSL shell or use .env
   export LEGAL_API_URL="http://localhost:8000/v1/query"
   export API_KEY="replace-with-your-api-key"
   export GEMINI_MODEL="gemini-2.5-flash"
   export ALLOW_LOCAL_MODEL_RUNTIME="0"
   python -m pip install -r requirements.txt
   python -m streamlit run app.py --server.port 8501 --server.headless true
6. Open browser to http://localhost:8501 (or use WSL host mapping)
7. In UI, choose Provider -> Custom API and ensure the app can call LEGAL_API_URL; provide API key in sidebar or set it as env.
8. Run test query and verify logs:
   # Backend logs
   docker compose logs -f api
   # Streamlit logs will be in the terminal where streamlit runs

Common issues on WSL
- Docker socket permission errors: ensure Docker Desktop WSL integration is enabled
- Networking: if using Windows browser to access WSL-hosted Streamlit, use localhost:8501
- Native library failures: local model containers may fail to start if HF_TOKEN or MODEL_ID incorrect

Cleanup
- docker compose -f docker-compose.example.yml down -v

This testing approach provides an environment close to the Ubuntu VM production setup and helps verify the end-to-end pipeline described in your query.