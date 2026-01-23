---
description: Implement technical plans from thoughts/shared/plans with verification
---

# Implement Plan

You are tasked with implementing an approved technical plan from `thoughts/shared/plans/`. These plans contain phases with specific changes and success criteria.

**This command runs AUTONOMOUSLY** - execute all phases without pausing for manual verification unless you encounter blockers.

## Getting Started

When given a plan path:
- Read the plan completely and check for any existing checkmarks (- [x])
- Read the original ticket and all files mentioned in the plan
- **Read files fully** - never use limit/offset parameters, you need complete context
- Think deeply about how the pieces fit together
- Create a todo list to track your progress
- Start implementing immediately

If no plan path provided, ask for one.

## Agent Delegation (MANDATORY)

**You MUST delegate implementation to specialized agents**:

### Backend Changes
Use the **backend-engineer** agent (Task tool with `subagent_type="backend-engineer"`) for:
- API endpoints
- Database models/migrations
- Service layer logic
- Backend tests
- Any Python/FastAPI code

### Frontend Changes
Use the **frontend-engineer** agent (Task tool with `subagent_type="frontend-engineer"`) for:
- React components
- UI logic and state management
- Frontend tests
- Any TypeScript/React code

### Agent Prompt Template
When delegating, provide comprehensive context:
```
Implement Phase [N] of the plan: [plan_path]

**Context**:
- Original ticket: [ticket_path]
- Phase objective: [brief description]

**Changes Required**:
[List specific changes from the plan for this phase]

**Success Criteria**:
[List success criteria from the plan]

**Files to Read First**:
[List relevant files the agent should read]

**Constraints**:
- Follow YAGNI principles
- No over-engineering
- Match existing code patterns
```

## Phase Execution Workflow

For EACH phase, follow this exact sequence:

### Step 1: Delegate Implementation
- Identify if changes are backend, frontend, or both
- Spawn appropriate agent(s) with full context
- If both backend and frontend: run backend-engineer FIRST, then frontend-engineer

### Step 2: Run ALL Tests (MANDATORY)
**ALL tests must pass before proceeding to the next phase**

**Read `docs/guides/testing.md`** for the complete list of test commands and requirements.

Key sections to follow:
- "Test Execution" - Contains all commands for backend tests, frontend unit tests, E2E tests
- "Task Completion Checklist" - Contains the exact checks required before marking complete
- "Quick Reference" - Contains the most common commands

**Determine which tests to run based on your changes**:
- Backend changes → Backend tests (Docker required)
- Frontend changes → Frontend unit tests + TypeScript check
- API contract changes → E2E tests (Docker backend required)
- Full-stack changes → All tests

**If ANY test fails**:
1. Delegate the fix to the appropriate agent (backend-engineer or frontend-engineer)
2. Re-run ALL tests
3. Repeat until ALL tests pass

### Step 3: Update Plan Progress
- Check off completed items in the plan file using Edit
- Update your todo list
- Proceed to next phase

## Implementation Philosophy

Plans are carefully designed, but reality can be messy. Your job is to:
- Follow the plan's intent while adapting to what you find
- Implement each phase fully before moving to the next
- Verify your work makes sense in the broader codebase context
- **Never skip test verification** - all tests must pass

When things don't match the plan exactly, think about why and adapt. The plan is your guide, but your judgment matters too.

If you encounter a BLOCKER that prevents progress:
- STOP and present the issue clearly:
  ```
  BLOCKER in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]
  Attempted solutions: [what you tried]

  Need human input to proceed.
  ```

## Resuming Work

If the plan has existing checkmarks:
- Trust that completed work is done
- Pick up from the first unchecked item
- Verify previous work only if something seems off

## Summary: Phase Checklist

For each phase, complete ALL of these:
- [ ] Delegate to backend-engineer (if backend changes)
- [ ] Delegate to frontend-engineer (if frontend changes)
- [ ] Run ALL relevant tests per `docs/guides/testing.md` (must pass)
- [ ] Update plan checkboxes
- [ ] Proceed to next phase

## Post-Implementation Cleanup

After ALL phases are complete but BEFORE committing:

### Step 1: Code Cleanup (Parallel)

Run TWO code-cleanup agents in parallel using the Task tool:

**Backend Code Cleanup:**
```
subagent_type: "code-cleanup"

Prompt:
"Clean up all backend code changes from this implementation.

Plan implemented: [plan_path]

Focus on:
- Python/FastAPI code quality and consistency
- Removing any debugging artifacts
- Ensuring proper error handling
- Matching existing backend patterns
- No functional changes - cleanup only

Review all Python files modified during this implementation."
```

**Frontend Code Cleanup:**
```
subagent_type: "code-cleanup"

Prompt:
"Clean up all frontend code changes from this implementation.

Plan implemented: [plan_path]

Focus on:
- React/TypeScript code quality and consistency
- Removing any debugging artifacts
- Ensuring proper error handling
- Matching existing frontend patterns
- No functional changes - cleanup only

Review all TypeScript/React files modified during this implementation."
```

### Step 2: Test Verification (Post-Cleanup)

**Read `docs/guides/testing.md`** and run ALL relevant tests.

**If ANY test fails:**
1. Delegate the fix to the appropriate agent (backend-engineer or frontend-engineer)
2. Re-run ALL tests
3. Repeat until ALL tests pass

### Step 3: Code Simplification

Run the code-simplifier agent:
```
Use Task tool with subagent_type: "code-simplifier:code-simplifier"

Prompt:
"Simplify and refine the code changes from this implementation.

Plan implemented: [plan_path]

Focus on recently modified files and apply refinements for clarity,
consistency, and maintainability while preserving all functionality."
```

This will analyze recently modified code and apply refinements for:
- Code clarity and consistency
- Reduced complexity and nesting
- Eliminated redundant code
- Improved naming
- Project-specific best practices

### Step 4: Test Verification (Post-Simplification)

**Run ALL tests again** after code simplification.

**If ANY test fails:**
1. Delegate the fix to the appropriate agent (backend-engineer or frontend-engineer)
2. Re-run ALL tests
3. Repeat until ALL tests pass

### Post-Implementation Checklist

Before proceeding to commit:
- [ ] Code-cleanup agents completed (backend + frontend)
- [ ] ALL tests pass after cleanup
- [ ] Code-simplifier skill completed
- [ ] ALL tests pass after simplification

## Final Phase: Commit and Open PR

After ALL phases are complete, post-implementation cleanup is done, and ALL tests pass, create a PR:

### Step 1: Prepare the Branch
```bash
# Check current branch
git branch --show-current

# If on main, create a feature branch based on the plan name
# Example: feat/live20-progressive-results

# Fetch and rebase on latest main
git fetch origin main
git stash  # if there are uncommitted changes
git rebase origin/main
git stash pop  # if stashed
```

### Step 2: Stage and Commit
- Run `git status` to see all changes
- Run `git diff` to understand modifications
- Stage all related files (use specific paths, not `git add -A`)
- Create a descriptive commit message:
  - Use imperative mood (e.g., "Add progressive results display")
  - Reference the ticket/plan in the body if helpful
  - **Do NOT add Co-Authored-By or Claude attribution**

Example commit format:
```
feat(component): Brief description of changes

- Bullet point of key change 1
- Bullet point of key change 2
```

### Step 3: Push and Create PR
```bash
# Push to remote (create upstream tracking)
git push -u origin <branch-name>

# Create PR using gh CLI
gh pr create --title "feat(component): Brief description" --body "$(cat <<'EOF'
## Summary
- Key change 1
- Key change 2

## Test Plan
- [ ] Manual verification step 1
- [ ] Manual verification step 2

## Ticket
Link to thoughts/shared/tickets/... if applicable
EOF
)"
```

### Step 4: Report to User
- Provide the PR URL
- List any remaining manual verification steps
- Note if there are pre-existing test failures unrelated to the changes

Remember: You're implementing a solution autonomously. Keep moving forward, ensure quality through tests, and only stop for true blockers.
