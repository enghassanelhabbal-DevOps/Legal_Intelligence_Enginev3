Backend Deployment Guide (Linux VM)

This guide shows how to deploy the FastAPI backend and optional local model container on an Ubuntu 24.04 LTS VM. It includes the exact values and paths used by this project so the Streamlit UI (app.py) and backend interoperate out-of-the-box.

Assumptions & project values
- Streamlit UI entrypoint: app.py (root)
- Backend API path: /v1/query
- Default artifacts path used by API: artifacts_api (created automatically)
- Example documents filename: legal_documents.json (also accepts data/legal_documents.json)
- Default Gemini model (env): gemini-2.5-flash
- Default OpenAI model (env): gpt-5-mini

Pre-flight on VM (Ubuntu 24.04)
1. Update and install prerequisites:
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y docker.io docker-compose git nginx certbot
2. Clone repo and copy example env:
   git clone https://github.com/enghassanelhabbal-DevOps/legal_rag_engine.git
   cd legal_rag_engine
   git checkout agents/devops-mlops-streamlit-integration
   cp .env.example .env
   # Edit .env and set API_KEY, HF_TOKEN, GEMINI_MODEL, etc.

Docker-compose (example)
- File: docker-compose.example.yml
- Run:
   docker compose -f docker-compose.example.yml up -d --build

Nginx & TLS
- Use certbot to request a certificate for your domain after DNS points to VM:
   sudo certbot --nginx -d your-backend.example.com
- Ensure /etc/nginx/.htpasswd exists if you use basic auth (htpasswd -c /etc/nginx/.htpasswd user)

Streamlit configuration (Cloud)
- In Streamlit Secrets (TOML) set:
  LEGAL_API_URL = "https://your-backend.example.com/v1/query"
  API_KEY = "<the same value you set in .env>"
  ALLOW_LOCAL_MODEL_RUNTIME = "0"
  GEMINI_MODEL = "gemini-2.5-flash"
  OPENAI_MODEL = "gpt-5-mini"

Testing
- API health:
   curl -v -H "x-api-key: $API_KEY" https://your-backend.example.com/v1/health
- API query:
   curl -s -H "Content-Type: application/json" -H "x-api-key: $API_KEY" \
     -X POST https://your-backend.example.com/v1/query -d '{"query":"ما حكم التلبس؟","top_k":5}' | jq .

Troubleshooting common errors
- 401 Invalid API key: ensure x-api-key header matches API_KEY in .env
- 404 Documents file not found: place legal_documents.json in repo root or data/legal_documents.json
- Model container not starting: check HF_TOKEN and MODEL_ID in .env
- Port conflicts: ensure ports 80/443 free for nginx; API listens on 8000

Logs
- API logs: docker logs -f <api container id>
- Nginx logs: sudo journalctl -u nginx or /var/log/nginx/error.log

Security notes
- Do not expose model container without protection. Keep model service on internal network and only expose nginx proxy.
- Rotate API keys and store secrets in a secret manager.

