# CLAUDE.md

## Project
Trading Analyst — a stock analysis app built as a learning project.

## Commands
- Backend: `./scripts/dc.sh up -d` (start), `./scripts/dc.sh exec backend-dev pytest` (test)
- Frontend: `cd frontend && npm run dev` (start), `npm run test:unit` (test)
- Never use docker compose directly — always `./scripts/dc.sh`

## Structure
- backend/ — FastAPI + PostgreSQL (Python 3.11)
- frontend/ — React 19 + Vite + Tailwind + ShadCN (TypeScript)
- progress.json — course progress state
- student.json — student preferences

## Rules
- Frontend is permanently dark mode — never use `dark:` Tailwind prefix
- Colors come from src/constants/colors.ts — no magic hex values
- All interactive elements need data-testid attributes
- API responses follow standard envelope (see lessons for details)
