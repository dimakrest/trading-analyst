---
description: Debug issues by investigating logs, database state, and git history
---

# Debug

You are tasked with helping debug issues during manual testing or implementation. This command allows you to investigate problems by examining logs, database state, and git history without editing files. Think of this as a way to bootstrap a debugging session without using the primary window's context.

## Initial Response

When invoked WITH a plan/ticket file:
```
I'll help debug issues with [file name]. Let me understand the current state.

What specific problem are you encountering?
- What were you trying to test/implement?
- What went wrong?
- Any error messages?

I'll investigate the logs, database, and git state to help figure out what's happening.
```

When invoked WITHOUT parameters:
```
I'll help debug your current issue.

Please describe what's going wrong:
- What are you working on?
- What specific problem occurred?
- When did it last work?

I can investigate logs, database state, and recent changes to help identify the issue.
```

## Environment Information

You have access to these key locations and tools:

**Logs** (Docker container logs):
- Backend logs: `./scripts/dc.sh logs backend-dev`
- Database logs: `./scripts/dc.sh logs postgres-dev`
- All services: `./scripts/dc.sh logs`
- Real-time: Add `--follow` flag
- Last N lines: Add `--tail=N` flag

**Database**:
- PostgreSQL database running in Docker
- Connect: `./scripts/dc.sh exec postgres-dev psql -U trader -d trading_analyst_dev`
- Tables: setups, trades, monitoring_events, detectors, indicators, etc.
- Check schema: `\dt` and `\d table_name`

**Git State**:
- Check current branch, recent commits, uncommitted changes
- Similar to how `commit` and `describe_pr` commands work

**Service Status**:
- Check Docker services: `./scripts/dc.sh ps`
- Backend health: `./scripts/dc.sh exec backend-dev curl -f http://localhost:8000/health`
- Database status: `./scripts/dc.sh exec postgres-dev pg_isready`

## Process Steps

### Step 1: Understand the Problem

After the user describes the issue:

1. **Read any provided context** (plan or ticket file):
   - Understand what they're implementing/testing
   - Note which phase or step they're on
   - Identify expected vs actual behavior

2. **Quick state check**:
   - Current git branch and recent commits
   - Any uncommitted changes
   - When the issue started occurring

### Step 2: Investigate the Issue

Spawn parallel Task agents for efficient investigation:

```
Task 1 - Check Recent Logs:
Find and analyze Docker logs for errors:
1. Check backend logs: ./scripts/dc.sh logs backend-dev --tail=100
2. Check database logs: ./scripts/dc.sh logs postgres-dev --tail=50
3. Search for ERROR, CRITICAL, or exception messages
4. Look for stack traces, repeated errors, or connection issues
5. Note timestamps around when the issue started
Return: Key errors/warnings with timestamps
```

```
Task 2 - Database State:
Check the current database state:
1. Check database is running: ./scripts/dc.sh exec postgres-dev pg_isready
2. Query relevant tables based on the issue:
   - Recent setups: ./scripts/dc.sh exec postgres-dev psql -U trader -d trading_analyst_dev -c "SELECT * FROM setups ORDER BY created_at DESC LIMIT 5;"
   - Recent trades: ./scripts/dc.sh exec postgres-dev psql -U trader -d trading_analyst_dev -c "SELECT * FROM trades ORDER BY created_at DESC LIMIT 5;"
   - Monitoring events: ./scripts/dc.sh exec postgres-dev psql -U trader -d trading_analyst_dev -c "SELECT * FROM monitoring_events ORDER BY created_at DESC LIMIT 10;"
3. Check for NULL values, stuck states, or data anomalies
Return: Relevant database findings
```

```
Task 3 - Git and File State:
Understand what changed recently:
1. Check git status and current branch
2. Look at recent commits: git log --oneline -10
3. Check uncommitted changes: git diff
4. Verify expected files exist
5. Look for any file permission issues
Return: Git state and any file issues
```

### Step 3: Present Findings

Based on the investigation, present a focused debug report:

```markdown
## Debug Report

### What's Wrong
[Clear statement of the issue based on evidence]

### Evidence Found

**From Logs** (Docker containers):
- [Error/warning with timestamp]
- [Pattern or repeated issue]

**From Database**:
```sql
-- Relevant query and result
[Finding from database]
```

**From Git/Files**:
- [Recent changes that might be related]
- [File state issues]

### Root Cause
[Most likely explanation based on evidence]

### Next Steps

1. **Try This First**:
   ```bash
   [Specific command or action]
   ```

2. **If That Doesn't Work**:
   - Restart services: `./scripts/dc.sh restart`
   - Rebuild containers: `./scripts/dc.sh up --build -d`
   - Check frontend console: F12 in browser for JavaScript errors

### Can't Access?
Some issues might be outside my reach:
- Browser console errors (F12 in browser)
- Docker host system issues
- External API failures (Yahoo Finance, broker APIs)

Would you like me to investigate something specific further?
```

## Important Notes

- **Focus on manual testing scenarios** - This is for debugging during implementation
- **Always require problem description** - Can't debug without knowing what's wrong
- **Read files completely** - No limit/offset when reading context
- **Think like `commit` or `describe_pr`** - Understand git state and changes
- **Guide back to user** - Some issues (browser console, MCP internals) are outside reach
- **No file editing** - Pure investigation only

## Quick Reference

**View Logs**:
```bash
./scripts/dc.sh logs backend-dev --tail=100      # Backend logs
./scripts/dc.sh logs postgres-dev --tail=50      # Database logs
./scripts/dc.sh logs --tail=100                  # All services
./scripts/dc.sh logs --follow backend-dev        # Real-time backend logs
```

**Database Queries**:
```bash
./scripts/dc.sh exec postgres-dev pg_isready                                           # Check DB is running
./scripts/dc.sh exec postgres-dev psql -U trader -d trading_analyst_dev -c "\dt"      # List tables
./scripts/dc.sh exec postgres-dev psql -U trader -d trading_analyst_dev -c "SELECT * FROM setups ORDER BY created_at DESC LIMIT 5;"
./scripts/dc.sh exec postgres-dev psql -U trader -d trading_analyst_dev -c "SELECT * FROM monitoring_events ORDER BY created_at DESC LIMIT 10;"
```

**Service Check**:
```bash
./scripts/dc.sh ps                                                  # Check all services
./scripts/dc.sh exec backend-dev curl -f http://localhost:8000/health   # Backend health
./scripts/dc.sh exec postgres-dev pg_isready                            # Database status
```

**Git State**:
```bash
git status
git log --oneline -10
git diff
```

Remember: This command helps you investigate without burning the primary window's context. Perfect for when you hit an issue during manual testing and need to dig into logs, database, or git state.
