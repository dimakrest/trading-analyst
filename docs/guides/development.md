# Development Guide

## Environment Setup

### Quick Start

**Development** (auto-configured per clone):

```bash
# Single terminal (Docker in background)
./scripts/dc.sh up -d && cd frontend && npm run dev

# Or two terminals:
# Terminal 1: ./scripts/dc.sh up
# Terminal 2: cd frontend && npm run dev
```

On first run, `./scripts/dc.sh` automatically:
1. Generates `.env.dev` with unique project name and ports based on directory name
2. Creates isolated analytics directory
3. Starts postgres and backend containers

The frontend runs locally (not in Docker) to avoid `node_modules` sync issues between macOS and Linux.

Check your generated `.env.dev` for exact port values.

**Production** (fixed configuration):
```bash
./scripts/prod.sh
```
- Frontend: http://localhost:5177
- Backend: http://localhost:8093
- Database: localhost:5440

### Database Migrations

```bash
# Dev - use the wrapper script:
./scripts/dc.sh exec backend-dev alembic upgrade head
./scripts/dc.sh exec backend-dev alembic revision --autogenerate -m "description"

# Prod (fixed name)
docker exec trading_analyst_prod-backend-prod-1 alembic upgrade head
```

### Stopping Environments

```bash
# Dev - use the wrapper script
./scripts/dc.sh down

# Prod
docker compose -f docker-compose.prod.yml down
```

### Multi-Instance Support

Each clone automatically gets isolated:
- **Project name**: Derived from directory name (e.g., `trading_analyst_3_dev`)
- **Ports**: Deterministic hash of directory name (range: postgres 5500-5599, backend 8100-8199)
- **Frontend**: Runs locally on port from `.env.dev` (FRONTEND_PORT, used by Vite)
- **Volumes**: Prefixed with project name
- **Analytics**: `{project_directory}/analytics`

To regenerate configuration: delete `.env.dev` and run `./scripts/dc.sh` again.

---

## Database Operations

```bash
# Generate migration
cd backend && alembic revision --autogenerate -m "Add new table"
alembic upgrade head
```

---

## Configuration

| File | Purpose |
|------|---------|
| `.env.dev` | Auto-generated dev config (unique per clone) |
| `.env.dev.example` | Template/reference for dev config |
| `docker-compose.prod.yml` | Fixed prod configuration |

**Execution Guardrails** (env vars):
- `MAX_ORDER_VALUE` (default: 1000.0)
- `ACCOUNT_BALANCE` (default: 2000.0)
- `MAX_DAILY_TRADES` (default: 3)
- `MAX_STOP_LOSS_DISTANCE` (default: 0.10)

---

## Troubleshooting

```bash
# View logs
./scripts/dc.sh logs backend-dev
./scripts/dc.sh logs postgres-dev

# Restart services
./scripts/dc.sh restart backend-dev
```
