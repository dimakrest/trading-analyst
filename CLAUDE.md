# CLAUDE.md

This file provides universal guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

Trading Analyst is a **local-first** human-in-the-loop semi-automated trading system for a small team (2-3 users). Combines human pattern recognition with systematic validation and execution.

**Quality Standards**: This system handles **real money**. Quality is non-negotiable:
- All changes must be thoroughly tested
- Edge cases must be handled gracefully
- Error handling must be robust
- No shortcuts in trading logic

**Core Concept**:
- **Human**: Identifies potential trading setups, provides symbol + breakout price
- **System**: Validates setup quantitatively, monitors for optimal entry, executes trade through broker integration with perfect discipline

---

## Agent-Specific Context

**Different agents need different context to avoid pollution**. See the appropriate file for your role:

**Global context** (in `~/.claude/context/`, applies to all projects):
- **Code Research Agents** - See global `CODE_RESEARCH.md`
- **Complete Workflow** - See global `WORKFLOW.md`

**Project-specific context** (in `.claude/context/`):
- **Backend Execution** (backend-engineer): See `.claude/context/BACKEND_EXECUTION.md`
- **Frontend Execution** (frontend-engineer): See `.claude/context/FRONTEND_EXECUTION.md`

---

## Universal Rules (Apply to ALL Agents)

### 1. Agent Delegation (MANDATORY for ALL Agents)

**YOU MUST DELEGATE tasks to specialized agents when appropriate**

**When to Delegate**:
- **Backend bugs/debugging** → backend-engineer agent (see `.claude/context/BACKEND_EXECUTION.md`)
- **Frontend bugs/debugging** → frontend-engineer agent (see `.claude/context/FRONTEND_EXECUTION.md`)
- **Code research** → codebase research agents (global)
- **Planning** → /create_plan command (global)
- **Any task requiring > 30 minutes of investigation** → appropriate specialized agent

**Why Delegation is Mandatory**:
- Specialized agents have deeper expertise and focused context
- Prevents shortcuts and superficial fixes
- Ensures thorough investigation
- Better problem-solving outcomes

**How to Delegate**:
```
Use the Task tool with appropriate subagent_type
Provide clear context and expected outcomes
Wait for agent to complete before proceeding
```

### 2. Documentation Management

**NEVER keep old documentation files** - they are extremely confusing and harmful.

- **ALWAYS DELETE** outdated files immediately when consolidating
- **NO archive folders** - delete completely, don't move
- **One source of truth** per topic only

### 3. No Speculation Without Sources (CRITICAL)

**When speculating, estimating, or inferring - ALWAYS STATE EXPLICITLY that it's speculation**

Use phrases like:
- "I'm speculating that..."
- "Based on my inference (not documented)..."
- "This is my estimate, not from official sources..."
- "I don't have hard data for this, but my reasoning is..."

**ALWAYS verify speculations with web search before presenting them as facts**:
- Use WebSearch or mcp__perplexity__perplexity_search_web to find documented evidence
- Search for GitHub issues, Stack Overflow posts, official documentation
- If no evidence found, clearly state "I cannot find documentation for this"
- Be critical of your own explanations - if you're inferring, verify first

**User should be able to trust your technical explanations are backed by sources.**

### 4. Clean Up After Yourself

**ALWAYS delete temporary files that you create**

- Test files created for debugging
- Temporary scripts
- Backup files (unless explicitly requested to keep)
- Downloaded data for testing

### 5. Never Kill Unknown Processes

**NEVER stop processes that you are not the one who started them!**

**ALWAYS ask for permission to kill unknown processes**

- Check what started a process before killing it
- If uncertain, ask the user first
- Document what processes you start so you know what's yours

### 6. Docker Commands

**ALWAYS use the wrapper script for all Docker operations:**

```bash
./scripts/dc.sh <command>
```

This script:
- Auto-generates `.env.dev` on first run (unique ports per clone)
- Ensures correct project context for all commands
- Prevents orphan containers and port conflicts

**Examples:**
```bash
# Start services
./scripts/dc.sh up -d

# View status
./scripts/dc.sh ps

# View logs
./scripts/dc.sh logs -f backend-dev

# Run commands in container
./scripts/dc.sh exec backend-dev pytest
./scripts/dc.sh exec backend-dev alembic upgrade head

# Stop services
./scripts/dc.sh down
```

**NEVER run `docker compose` directly** - it will target wrong project or create orphan containers.

### 7. Testing

**`docs/guides/testing.md` is the single source of truth for all testing guidance.**

Read it before running any tests.

---

**Workflow Artifacts** (thoughts/shared/):
- `thoughts/shared/tickets/` - Task descriptions
- `thoughts/shared/plans/` - Implementation plans
- `thoughts/shared/research/` - Codebase research
- `thoughts/shared/prs/` - PR documentation

## Remember

This CLAUDE.md contains **project-specific rules**.

For detailed instructions specific to your role:
- **Global context files** are in `~/.claude/context/` (CODE_RESEARCH.md, WORKFLOW.md)
- **Project context files** are in `.claude/context/` (BACKEND_EXECUTION.md, FRONTEND_EXECUTION.md)
- Delegate to specialized agents when appropriate

**The goal**: Eliminate context pollution while ensuring every agent knows exactly what they need to know.
