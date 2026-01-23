#!/bin/bash
# Single wrapper for all docker compose commands
# Auto-generates .env.dev on first run

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Generate .env.dev if missing
if [[ ! -f "$PROJECT_ROOT/.env.dev" ]]; then
    echo "First run - generating .env.dev..."

    DIR_NAME="$(basename "$PROJECT_ROOT")"

    # Create deterministic port offset from directory name hash (0-99 range)
    # This ensures same directory always gets same ports
    # Use md5sum on Linux, md5 on macOS
    if command -v md5sum &> /dev/null; then
        HASH=$(echo -n "$DIR_NAME" | md5sum | cut -c1-4)
    else
        HASH=$(echo -n "$DIR_NAME" | md5 | cut -c1-4)
    fi
    PORT_OFFSET=$((16#$HASH % 100))

    # Base ports + offset (ensures unique ports per clone)
    POSTGRES_PORT=$((5500 + PORT_OFFSET))
    BACKEND_PORT=$((8100 + PORT_OFFSET))
    FRONTEND_PORT=$((5200 + PORT_OFFSET))

    # Sanitize directory name for Docker (replace invalid chars with underscore)
    PROJECT_NAME=$(echo "$DIR_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]/_/g')

    # Analytics path - uses project directory for portability
    ANALYTICS_PATH="${PROJECT_ROOT}/analytics"

    cat > "$PROJECT_ROOT/.env.dev" << EOF
# Auto-generated for: $DIR_NAME
# Regenerate by deleting this file and running ./scripts/dc.sh

# ============================================
# DOCKER COMPOSE PROJECT (Unique per clone)
# ============================================
COMPOSE_PROJECT_NAME=${PROJECT_NAME}_dev

# ============================================
# PORT CONFIGURATION (Derived from directory hash)
# ============================================
POSTGRES_PORT=${POSTGRES_PORT}
BACKEND_PORT=${BACKEND_PORT}

# Frontend runs locally (not in Docker) - this port is used by Vite
FRONTEND_PORT=${FRONTEND_PORT}

# ============================================
# DATABASE CONFIGURATION
# ============================================
POSTGRES_DB=trading_analyst_dev
POSTGRES_USER=trader
POSTGRES_PASSWORD=localpass
DATABASE_URL=postgresql+asyncpg://trader:localpass@postgres-dev:5432/trading_analyst_dev

# ============================================
# APPLICATION SETTINGS
# ============================================
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# ============================================
# CORS CONFIGURATION
# ============================================
CORS_ORIGINS=http://localhost:${FRONTEND_PORT},http://localhost:${BACKEND_PORT}

# ============================================
# DOCKER NETWORKING
# ============================================
DOCKER_BACKEND_URL=http://backend-dev:8000

# ============================================
# ANALYTICS PATH (Isolated per clone)
# ============================================
ANALYTICS_PATH=${ANALYTICS_PATH}

# ============================================
# INTERACTIVE BROKERS CONFIGURATION
# ============================================
BROKER_TYPE=mock
IB_HOST=host.docker.internal
IB_PORT=4002
IB_CLIENT_ID=1
IB_DATA_CLIENT_ID=99

# ============================================
# MARKET DATA PROVIDER
# ============================================
# Options: 'yahoo' (default), 'ib', 'mock'
MARKET_DATA_PROVIDER=yahoo

EOF

    echo "Generated .env.dev with:"
    echo "  Project: ${PROJECT_NAME}_dev"
    echo "  Docker ports: postgres=$POSTGRES_PORT, backend=$BACKEND_PORT"
    echo "  Local frontend: http://localhost:$FRONTEND_PORT (run: cd frontend && npm run dev)"
    echo "  Analytics: $ANALYTICS_PATH"

    # Create analytics directory if it doesn't exist
    mkdir -p "$ANALYTICS_PATH"
fi

# Source the environment to get COMPOSE_PROJECT_NAME and port configs
# Use set -a to auto-export all variables so docker compose inherits them
set -a
source "$PROJECT_ROOT/.env.dev"
set +a

# Verify COMPOSE_PROJECT_NAME is set
if [[ -z "$COMPOSE_PROJECT_NAME" ]]; then
    echo "ERROR: COMPOSE_PROJECT_NAME not set in .env.dev"
    echo "Delete .env.dev and run ./scripts/dc.sh again to regenerate"
    exit 1
fi

# Run docker compose with the correct context
cd "$PROJECT_ROOT"
exec docker compose "$@"
