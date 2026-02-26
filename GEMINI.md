# Trading Analyst Context

## Project Overview
**Trading Analyst** is a local-first, human-in-the-loop, semi-automated trading system designed for a small team (2-3 users). It combines human pattern recognition with systematic validation and execution.

*   **Core Philosophy:** YAGNI (You Aren't Gonna Need It) for infrastructure, but **Quality is Non-Negotiable** for execution and safety.
*   **Goal:** Safe, disciplined execution of trades with "real money" stakes.

## Architecture
The project follows a dockerized microservices architecture:

*   **Frontend**: React (Vite, TypeScript) application for user interaction, chart visualization (lightweight-charts), and trade management.
*   **Backend**: Python (FastAPI) service handling business logic, database interactions, and broker/market data integrations.
*   **Agent**: Python service providing LLM analysis capabilities (Claude integration).
*   **Database**: PostgreSQL for persistent storage of trades, signals, and analysis.

## Development Environment
The project relies on Docker Compose for orchestration but uses a wrapper script for environment setup.

### Getting Started
**DO NOT** run `docker compose` directly. Use the wrapper script for all Docker operations:

```bash
./scripts/dc.sh up -d
```

This script handles:
*   Auto-generation of `.env.dev` on first run.
*   Creation of isolated analytics directories.
*   Multi-instance support.

### Key Commands

| Action | Context | Command |
| :--- | :--- | :--- |
| **Start Dev Env** | Root | `./scripts/dc.sh up -d` |
| **Stop Dev Env** | Root | `./scripts/dc.sh down` |
| **Docker Logs** | Root | `./scripts/dc.sh logs -f [service]` |
| **Docker Exec** | Root | `./scripts/dc.sh exec [service] bash` |

## Service Details & Conventions

### Backend (`/backend`)
*   **Stack**: Python 3.11+, FastAPI, SQLAlchemy (Async), Alembic, Pydantic.
*   **Key Tools**:
    *   **Test**: `pytest` (Unit, Integration, Slow markers).
    *   **Lint**: `ruff`, `black`, `flake8`.
    *   **Type Check**: `mypy`.
*   **Database**: Migrations managed via Alembic (`alembic upgrade head`).

### Frontend (`/frontend`)
*   **Stack**: React 19, Vite, TypeScript, Tailwind CSS, Radix UI.
*   **Key Scripts**:
    *   `npm run dev`: Start dev server.
    *   `npm run test`: Run unit/component tests (Vitest).
    *   `npm run test:e2e`: Run E2E tests (Playwright).
    *   `npm run lint`: Run ESLint.

### Agent (`/agent`)
*   **Stack**: Python, FastAPI.
*   **Role**: Specialized service for AI analysis of market data and code research.

## Development Guidelines (Crucial)

1.  **YAGNI**: Do not build complex infrastructure (Redis, Celery, User Auth) unless absolutely necessary.
2.  **Quality First**:
    *   Input validation is mandatory.
    *   Error handling must be robust (try/catch around external calls).
    *   **Tests are required** for all new logic (Unit & Integration).
3.  **No Speculation**: Explicitly state when speculating. Verify facts via search or codebase research.
4.  **Clean Up**: Delete temporary files and test artifacts after use.
5.  **Agent Delegation**: Use specific agents for deep dives:
    *   Backend bugs -> Backend Agent
    *   Frontend bugs -> Frontend Agent
    *   Architecture -> Architecture Agent

## Documentation Map
*   `CLAUDE.md`: Master guide for AI agents.
*   `docs/`: Detailed project documentation.
*   `.claude/context/`: Role-specific context files.
