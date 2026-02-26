#!/bin/bash
# Start production environment
# Uses fixed configuration from docker-compose.prod.yml

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo ""
echo "Starting production services (postgres, backend, agent)..."
echo ""
echo "Frontend runs locally. In another terminal:"
echo "  cd frontend && VITE_API_PROXY_TARGET=http://localhost:8093 npm run dev -- --port 5177"
echo ""

docker compose -f docker-compose.prod.yml up "$@"
