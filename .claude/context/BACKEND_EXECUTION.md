# Backend Execution Agent Instructions

**For**: backend-engineer, backend implementation

## Task Completion Definition

A task is ONLY complete when ALL are true:
- All tests passing (100%)
- Coverage >= 80% (adjust per project)
- Feature branch + PR created
- No known bugs
- API documentation updated (if modifying endpoints/schemas)

**NEVER** mark complete with failing tests or missing documentation.

---

## Testing Requirements

Check your project's testing documentation for specific commands.

**Coverage check is manual**: Always verify output shows adequate coverage.

---

## API Documentation Requirements

**Documentation is part of the implementation, not an afterthought.**

### When Modifying an Existing Endpoint

- Update `summary` if endpoint purpose changed
- Update `description` if behavior/parameters/response changed
- Update `responses` dict if new error codes possible
- Update docstring Args/Returns/Raises
- Update schema field descriptions if fields changed
- Verify at API docs endpoint (e.g., `/docs`, `/redoc`)

### When Creating a New Endpoint

Every new endpoint MUST have:
- response_model
- summary (3-8 words)
- description (2-4 sentences)
- operation_id (unique snake_case)
- responses (error codes)

### REST API Conventions

- URL paths use kebab-case
- Pagination uses standard structure with `items` key
- Follow existing patterns in the codebase

---

## Git Workflow (MANDATORY)

```bash
# 1. Create feature branch
git checkout -b feature/descriptive-name

# 2. Run ALL tests before committing

# 3. Commit
git add . && git commit -m "type: description"

# 4. Push and create PR
git push -u origin feature/descriptive-name
gh pr create --title "Title" --body "Description"
```

**NEVER**: Push directly to main, skip tests, mark complete without PR.

---

## Bug Fixing Rules

- NEVER use fake data to make tests pass
- NEVER add workarounds instead of fixing root cause
- Investigate deeply with logging
- Test with different inputs
- Delegate complex issues to specialized agents

---

## Completion Checklist

- [ ] Backend tests: 100% passing
- [ ] Coverage: >= threshold
- [ ] Feature branch: created
- [ ] PR: created
- [ ] API documentation: updated (if API changes made)

---

## Database Migrations (if using Alembic)

```bash
# Create migration
alembic revision --autogenerate -m "Add column"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Check status
alembic current
alembic history
```

**Best Practices**:
- Always review auto-generated migrations before applying
- Test rollbacks: `upgrade head` -> `downgrade -1` -> `upgrade head`
- Descriptive names: `add_index_to_patterns_symbol` not `update`
