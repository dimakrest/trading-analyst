# Trading Analyst Documentation

This documentation follows a YAGNI (You Aren't Gonna Need It) approach - documenting only what we're actually building.

## Documentation by Agent Type

Different agents have different contexts to avoid pollution. See the appropriate guide for your role:

- **Code Research** (codebase-locator, codebase-analyzer, codebase-pattern-finder, thoughts-locator, thoughts-analyzer)
  → Start with `.claude/context/CODE_RESEARCH.md`

- **Backend Implementation** (backend-engineer)
  → Start with `.claude/context/BACKEND_EXECUTION.md`, then see [Backend Testing](./backend/testing.md)

- **Frontend Implementation** (frontend-engineer)
  → Start with `.claude/context/FRONTEND_EXECUTION.md`, then see [Frontend Testing](./frontend/testing.md)

- **Planning** (/create_plan command)
  → See `.claude/context/WORKFLOW.md`

- **Complete Workflow** (all agents for reference)
  → See `.claude/context/WORKFLOW.md` for the full Ticket→Research→Plan→Implement→Test→Commit→PR flow

## Quick Navigation

### 📁 [Backend](./backend/)
- **[Testing](./backend/testing.md)** - Testing standards and practices

### 📁 [Frontend](./frontend/)
- **[Testing](./frontend/testing.md)** - Frontend testing standards
- **[Testing Checklist](./frontend/TESTING_CHECKLIST.md)** - UI testing checklist
- **[Design System](./frontend/DESIGN_SYSTEM.md)** - Colors, typography, components, and styling

### 📁 [Guides](./guides/)
- **[Development](./guides/development.md)** - Common development tasks
- **[Engineering Standards](./guides/engineering-standards.md)** - Code style and practices

## What We're Building (YAGNI Principle)

### ✅ Building NOW
- Human-in-the-loop trading system
- Pattern validation engine
- Trade execution with broker integration
- Stock price visualization with interactive charts
- PostgreSQL with simple schema
- FastAPI with service layer pattern
- React frontend with modern UI components
- Local development only

### ❌ NOT Building (Yet)
- Multiple broker integrations (start with one)
- Redis caching
- Background task queues
- WebSocket real-time updates
- Authentication system
- Complex monitoring

## Key Technologies

- **Backend**: FastAPI + PostgreSQL + Alembic
- **Frontend**: React + TypeScript + shadcn/ui + Lightweight Charts
- **Data**: Yahoo Finance (free, no API key)
- **Execution**: Broker API integration
- **Deployment**: Docker Compose (postgres + backend) + local frontend

## Performance Targets

- API response: <500ms
- Frontend render: 60 FPS
- Test coverage: >80%