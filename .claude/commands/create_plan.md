---
description: Create detailed implementation plans through interactive research and iteration
---

# Implementation Plan

You are tasked with creating detailed implementation plans through an interactive, iterative process. You should be skeptical, thorough, and work collaboratively with the user to produce high-quality technical specifications.

---

## Required Agent Consultation Matrix

**CRITICAL: Reference this table throughout the planning process.**

| Task Type | Required Agents | Consultation Point |
|-----------|-----------------|-------------------|
| Frontend-heavy | frontend-engineer | Before writing detailed plan |
| Backend-heavy | backend-engineer | Before writing detailed plan |
| Full-stack | frontend-engineer AND backend-engineer | Before writing detailed plan |
| Infrastructure | (context-dependent) | - |
| Documentation-only | (none required) | - |

**You MUST consult ALL required agents for your task type before writing the detailed plan. This is not optional.**

---

## Initial Response

When this command is invoked:

1. **Check if parameters were provided**:
   - If a file path or ticket reference was provided as a parameter, skip the default message
   - Immediately read any provided files FULLY
   - Begin with Phase 0: Task Classification

2. **If no parameters provided**, respond with:
```
I'll help you create a detailed implementation plan. Let me start by understanding what we're building.

Please provide:
1. The task/ticket description (or reference to a ticket file)
2. Any relevant context, constraints, or specific requirements
3. Links to related research or previous implementations

I'll analyze this information and work with you to create a comprehensive plan.

Tip: You can also invoke this command with a ticket file directly: `/create_plan thoughts/shared/tickets/2025-01-15-task-name.md`
```

Then wait for the user's input.

---

## Phase 0: Task Classification (REQUIRED - DO FIRST)

**Before ANY research, you must classify the task.**

### 0.1 Read the Ticket/Requirements

Read all mentioned files immediately and FULLY:
- Ticket files (e.g., `thoughts/shared/tickets/2025-01-15-task-name.md`)
- Research documents
- Related implementation plans
- **IMPORTANT**: Use the Read tool WITHOUT limit/offset parameters to read entire files

### 0.2 Classify the Task Type

Based on the ticket, explicitly declare the task type:

**Task Types:**
- **Frontend-heavy**: UI components, styling, UX flows, client-side state, accessibility, design system work
- **Backend-heavy**: APIs, database schema, business logic, services, migrations, worker processes
- **Full-stack**: Significant changes to BOTH frontend and backend (not just minor API consumption)
- **Infrastructure**: DevOps, CI/CD, configuration, deployment, monitoring
- **Documentation-only**: Documentation changes with no code modifications

### 0.3 Identify Required Agents

Based on your classification, identify which agents are REQUIRED:

| If Task Type is... | You MUST consult... |
|--------------------|---------------------|
| Frontend-heavy | frontend-engineer |
| Backend-heavy | backend-engineer |
| Full-stack | frontend-engineer AND backend-engineer |

**State explicitly**: "This is a [TYPE] task. Required agents: [LIST]"

---

## Step 1: Context Gathering & Initial Analysis

### 1.1 Spawn Research Agents

Spawn initial research tasks to gather context. Launch these in parallel:

**Core Research Agents (use as needed):**
- **codebase-locator** - Find all files related to the ticket/task
- **codebase-analyzer** - Understand how current implementation works
- **codebase-pattern-finder** - Find similar implementations to model after

**Historical Context (if relevant):**
- **thoughts-locator** - Find existing thoughts documents about this feature
- **thoughts-analyzer** - Extract key insights from relevant documents

Each agent will return specific file:line references.

### 1.2 Read Identified Files

After research tasks complete, read ALL files they identified as relevant into main context.

### 1.3 Present Initial Understanding

```
Based on the ticket and my research, I understand we need to [summary].

**Task Classification**: [Frontend-heavy / Backend-heavy / Full-stack / etc.]
**Required Agents**: [frontend-engineer / backend-engineer / both / none]

I've found that:
- [Current implementation detail with file:line reference]
- [Relevant pattern or constraint discovered]
- [Potential complexity or edge case identified]

Questions that my research couldn't answer:
- [Specific technical question]
- [Business logic clarification]
```

---

## Step 2: Required Agent Consultation

**This step is MANDATORY for Frontend-heavy, Backend-heavy, and Full-stack tasks.**

### 2.1 Consult Required Agents Based on Classification

**If Frontend-heavy or Full-stack, spawn frontend-engineer agent:**

Use the Task tool with `subagent_type: frontend-engineer` to review:
- Component architecture and structure
- Design aesthetics and consistency with existing UI
- Accessibility (ARIA attributes, keyboard navigation, focus management)
- ShadCN/Radix patterns usage
- User experience flow and potential friction points
- Responsive design considerations

Provide the agent with:
1. The proposed UI components and their structure
2. Any wireframes or design descriptions from the ticket
3. Specific questions about design decisions

Ask for specific recommendations, not just approval.

**If Backend-heavy or Full-stack, spawn backend-engineer agent:**

Use the Task tool with `subagent_type: backend-engineer` to review:
- API design and RESTful conventions
- Database schema and migrations
- Error handling and edge cases
- Security considerations
- Performance implications
- Testing strategy

Provide the agent with:
1. The proposed API endpoints and data models
2. Any schema changes or migrations needed
3. Specific questions about backend architecture

Ask for specific recommendations, not just approval.

### 2.2 Document Agent Recommendations

For each required agent consulted, document:
- Key recommendations (categorized by priority)
- Specific code patterns or approaches suggested
- Accessibility/security/performance concerns raised
- Changes to incorporate into the plan

### 2.3 Verification Checkpoint

**Before proceeding to Step 3, confirm:**

- [ ] Task type declared in Phase 0
- [ ] ALL required agents for that task type have been consulted
- [ ] Agent recommendations documented
- [ ] Key recommendations will be incorporated into plan

**DO NOT PROCEED TO STEP 3 if required agents have not been consulted.**

If you skipped a required agent, go back and consult them now.

---

## Step 3: Plan Structure Development

Once aligned on approach and agent recommendations are gathered:

### 3.1 Create Initial Plan Outline

```
Here's my proposed plan structure:

## Overview
[1-2 sentence summary]

## Implementation Phases:
1. [Phase name] - [what it accomplishes]
2. [Phase name] - [what it accomplishes]
3. [Phase name] - [what it accomplishes]

## Agent Recommendations Incorporated:
- [frontend-engineer]: [key items being incorporated]
- [backend-engineer]: [key items being incorporated]

Does this phasing make sense? Should I adjust the order or granularity?
```

### 3.2 Get Feedback on Structure

Get user buy-in before writing detailed plan.

---

## Step 4: Detailed Plan Writing

After structure approval:

### 4.1 Write the Plan File

Write to `thoughts/shared/plans/YYYY-MM-DD-description.md`

### 4.2 Use This Template Structure

```markdown
# [Feature/Task Name] Implementation Plan

## Task Classification

**Task Type**: [Frontend-heavy / Backend-heavy / Full-stack / Infrastructure / Documentation]

## Required Agent Consultations

| Agent | Consulted | Key Recommendations Incorporated |
|-------|-----------|----------------------------------|
| frontend-engineer | ✅ Yes / ⬜ N/A | [Brief summary of incorporated recommendations] |
| backend-engineer | ✅ Yes / ⬜ N/A | [Brief summary of incorporated recommendations] |

## Overview

[Brief description of what we're implementing and why]

## Current State Analysis

[What exists now, what's missing, key constraints discovered]

### Key Discoveries:
- [Important finding with file:line reference]
- [Pattern to follow]
- [Constraint to work within]

## Desired End State

[Specification of the desired end state and how to verify it]

## What We're NOT Doing

[Explicitly list out-of-scope items to prevent scope creep]

## Implementation Approach

[High-level strategy and reasoning]

---

## Phase 1: [Descriptive Name]

### Overview
[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File Group]
**File**: `path/to/file.ext`
**Changes**: [Summary of changes]

```[language]
// Specific code to add/modify
```

### Success Criteria:

#### Automated Verification:
- [ ] Read testing guide: `docs/guides/testing.md`
- [ ] Backend tests pass (100%): See testing guide for command
- [ ] Frontend tests pass (100%): See testing guide for command
- [ ] TypeScript 0 errors: See testing guide for command

#### Manual Verification:
- [ ] Feature works as expected when tested via UI
- [ ] [Specific manual test steps]

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to the next phase.

---

## Phase 2: [Descriptive Name]

[Similar structure...]

---

## Testing Strategy

### Unit Tests:
- [What to test]
- [Key edge cases]

### Integration Tests:
- [End-to-end scenarios]

### Manual Testing Steps:
1. [Specific step to verify feature]
2. [Another verification step]

## References

- Original ticket: `thoughts/shared/tickets/YYYY-MM-DD-task.md`
- Agent consultations: [frontend-engineer / backend-engineer recommendations incorporated above]
```

---

## Step 5: User Review

Present the draft plan location and gather feedback:

```
I've created the implementation plan at:
`thoughts/shared/plans/YYYY-MM-DD-description.md`

**Agent Consultations Completed:**
- [x] frontend-engineer (if applicable)
- [x] backend-engineer (if applicable)

Please review and let me know:
- Are the phases properly scoped?
- Are the success criteria specific enough?
- Any technical details that need adjustment?
```

Iterate based on feedback until user is satisfied.

---

## Step 6: Gemini Final Review

After user approves the plan structure:

### 6.1 Invoke Gemini Review

Use the `/gemini_plan_review` command on the plan file.

### 6.2 Incorporate Feedback

- Apply CRITICAL and IMPORTANT feedback to the plan
- Document what was/wasn't applied with reasoning

### 6.3 Present Summary

```
Gemini review complete. Changes incorporated:

**Applied:**
- [Change description]

**Not Applied (with reasoning):**
- [Feedback]: [Reason]
```

---

## Important Guidelines

### Bug Fixes Require Regression Tests First

For bug fix tickets, ALWAYS start with tests that reproduce the bug:
1. Write tests that FAIL on current (buggy) code
2. Implement the fix
3. Verify tests now PASS

### Be Skeptical
- Question vague requirements
- Identify potential issues early
- Don't assume - verify with code

### Be Interactive
- Don't write the full plan in one shot
- Get buy-in at each major step
- Allow course corrections

### Be Thorough
- Read all context files COMPLETELY
- Research actual code patterns using agents
- Include specific file paths and line numbers
- Write measurable success criteria

### No Open Questions in Final Plan
- If you encounter open questions, STOP
- Research or ask for clarification immediately
- Do NOT write plan with unresolved questions

### Track Progress
- Use TodoWrite to track planning tasks
- Update todos as you complete research

---

## Checklist: Before Finalizing Any Plan

- [ ] Phase 0 completed: Task type explicitly declared
- [ ] Required agents consulted based on task type matrix
- [ ] Agent recommendations documented and incorporated
- [ ] Plan template "Required Agent Consultations" table filled in
- [ ] User has reviewed and approved structure
- [ ] Gemini review completed and feedback incorporated
- [ ] No open questions remain
