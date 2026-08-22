#!/usr/bin/env bash
set -euo pipefail

# Simple integration test script for CI/local WSL
# Builds the api image, runs it mounting the repo so documents are available, waits for health, and runs a sample query.

IMAGE=legal_rag_api_test
CONTAINER=legal_rag_api_test_container
PORT=8000
API_KEY=${API_KEY:-test-key}

echo "Building api image..."
docker build -t $IMAGE -f api/Dockerfile ./api

# ensure a minimal documents file exists at repo root
cat > legal_documents.json <<'JSON'
[
  {"document_id":"sample-1","law_name":"قانون الإجراءات الجنائية","article_id":"1","content":"المحتوى الاختباري للمادة 1","metadata":{"title":"المادة 1 - قانون الإجراءات الجنائية"}}
]
JSON

# Run container with repo mounted so the API can find legal_documents.json
docker rm -f $CONTAINER 2>/dev/null || true

docker run -d --name $CONTAINER -p ${PORT}:8000 -e API_KEY=$API_KEY -v "$PWD":/app $IMAGE

echo "Waiting for health..."
for i in {1..15}; do
  if curl -s -H "x-api-key: $API_KEY" "http://localhost:${PORT}/v1/health" | grep -q ok; then
    echo "Health OK"
    break
  fi
  echo "waiting... ($i)"
  sleep 2
done

# Run a query
RESPONSE=$(curl -s -X POST "http://localhost:${PORT}/v1/query" -H "Content-Type: application/json" -H "x-api-key: $API_KEY" -d '{"query":"ما هي شروط التلبس؟","top_k":3}')

echo "Query response: $RESPONSE"

# Cleanup
docker rm -f $CONTAINER
rm -f legal_documents.json

echo "Integration test completed."
