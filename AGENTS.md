# AGENTS.md

This repository is **AI-first** and was created with **Claude Code (CC)**.  
When working here, preserve CC conventions and workflows unless the user explicitly asks to change them.

## Project Summary

Trading Analyst is a local-first, human-in-the-loop trading system.  
Quality and safety are strict requirements because behavior can affect real-money decisions.

## Working Rules

1. Use `./scripts/dc.sh` for Docker operations. Do not run `docker compose` directly.
2. Use `docs/guides/testing.md` as the testing source of truth before choosing test scope/commands.
3. Prefer robust, tested changes over shortcuts. Handle edge cases and failures explicitly.
4. If making an inference, label it clearly as an inference.
5. Never kill processes you did not start without explicit user approval.
6. Clean up temporary files and one-off artifacts you create.

## CC Compatibility (Important)

This codebase already has an established Claude Code workflow. Keep it intact:

- Primary guidance: `CLAUDE.md`
- Workflow config/context: `.claude/`
- Canonical workflow: `.claude/context/WORKFLOW.md`
- Role-specific execution guides:
  - `.claude/context/BACKEND_EXECUTION.md`
  - `.claude/context/FRONTEND_EXECUTION.md`
  - `.claude/context/CODE_RESEARCH.md`
- Existing workflow artifacts:
  - `thoughts/shared/tickets/`
  - `thoughts/shared/research/`
  - `thoughts/shared/plans/`
  - `thoughts/shared/prs/`

When adding docs or automation, align with these structures instead of introducing parallel systems.

### CC Workflow Stages

`Ticket -> Research -> Plan -> Implement -> Test -> Commit -> PR -> Merge`

### CC Command Set

- `/research_codebase`
- `/create_plan`
- `/implement_plan`
- `/commit`
- `/describe_pr`
- `/debug`

## Repo Map

- `backend/`: FastAPI, SQLAlchemy, Alembic, trading/business logic
- `frontend/`: React + TypeScript UI
- `docs/`: Development and testing guides
- `scripts/`: Environment/bootstrap helpers (`dc.sh`, setup scripts)

## Common Commands

```bash
# Start dev stack
./scripts/dc.sh up -d

# Stop dev stack
./scripts/dc.sh down

# Backend tests (inside container)
./scripts/dc.sh exec backend-dev pytest
```
