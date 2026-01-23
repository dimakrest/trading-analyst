# Complete Development Workflow

```
Ticket → Research → Plan → Implement → Test → Commit → PR → Merge
```

---

## Stage 1: Ticket

**Location**: `thoughts/shared/tickets/YYYY-MM-DD-description.md`

**Contents**: Problem, requirements, acceptance criteria, out-of-scope (YAGNI!)

---

## Stage 2: Research

**Command**: `/research_codebase [question]`

**Agents**: codebase-locator, codebase-analyzer, codebase-pattern-finder

**Output**: `thoughts/shared/research/YYYY-MM-DD-topic.md`

**Exit**: Current implementation understood, patterns identified

---

## Stage 3: Plan

**Command**: `/create_plan [ticket_path]`

**Process**:
1. Read ticket + research fully
2. Research codebase
3. Get design buy-in
4. Write plan with phased approach

**Output**: `thoughts/shared/plans/YYYY-MM-DD-description.md`

**Exit**: Plan approved, no open questions

---

## Stage 4: Implement

**Command**: `/implement_plan [plan_path]`

**Process**:
1. Create feature branch
2. For each phase:
   - Implement changes
   - Run tests (STOP if fail)
   - Manual verification
   - Get user confirmation

**Exit**: All features implemented, all tests passing

---

## Stage 5: Test

**Commands**: See project's testing documentation for specific commands.

**Requirements**:
- All tests: 100% pass rate
- Coverage: >= 80%
- E2E: 100% pass (MANDATORY if applicable)
- Type checks: 0 errors

---

## Stage 6: Commit

**Command**: `/commit`

```bash
git add .
git commit -m "type: description

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

**NEVER**: Commit to main, skip tests, force push

---

## Stage 7: Pull Request

**Command**: `/describe_pr`

```bash
git push -u origin feature/name
gh pr create --title "Title" --body "Description"
```

---

## Stage 8: Merge

1. PR reviewed and approved
2. Merge to main
3. Delete feature branch

---

## When to Delegate

| Situation | Delegate To |
|-----------|-------------|
| Backend complexity | backend-engineer |
| Frontend complexity | frontend-engineer |
| Code investigation | codebase-analyzer |

---

## Key Commands

| Command | Purpose |
|---------|---------|
| `/research_codebase` | Codebase research |
| `/create_plan` | Interactive planning |
| `/implement_plan` | Execute plans |
| `/commit` | Smart commits |
| `/describe_pr` | PR descriptions |
| `/debug` | Issue investigation |
