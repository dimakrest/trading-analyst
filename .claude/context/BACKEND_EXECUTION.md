# Backend Execution Agent Instructions

**For**: backend-engineer, backend implementation

## Task Completion Definition

A task is ONLY complete when ALL are true:
- ✅ All tests passing (100%)
- ✅ Coverage >= 80%
- ✅ Smoke tests passing
- ✅ Feature branch + PR created
- ✅ No known bugs
- ✅ API documentation updated (if modifying endpoints/schemas)

**NEVER** mark complete with failing tests, < 80% coverage, or missing API documentation.

---

## Testing Requirements

When running tests, read `docs/guides/testing.md`.

**Coverage check is manual**: Always check output shows >= 80%.

---

## API Documentation Requirements (MANDATORY)

**Documentation is part of the implementation, not an afterthought.**

### When Modifying an Existing Endpoint

- [ ] Update `summary` if endpoint purpose changed
- [ ] Update `description` if behavior/parameters/response changed
- [ ] Update `responses` dict if new error codes possible
- [ ] Update docstring Args/Returns/Raises
- [ ] Update Pydantic schema field descriptions if fields changed
- [ ] Update `json_schema_extra` examples if response structure changed
- [ ] Verify at `/docs` and `/redoc`

### When Creating a New Endpoint

Every new endpoint MUST have:
```python
@router.get(
    "/path",
    response_model=ResponseSchema,        # Required
    summary="Brief Action Description",   # Required: 3-8 words
    description="Detailed explanation...",# Required: 2-4 sentences
    operation_id="unique_snake_case_id",  # Required
    responses={400: {...}, 404: {...}}    # Required: error codes
)
```

**Pattern to follow**: `/backend/app/api/v1/stocks.py`

### REST API Conventions

When creating or modifying endpoints, read `docs/guides/engineering-standards.md` section 8.

### When Modifying Pydantic Schemas

Every field MUST have description:
```python
field_name: FieldType = Field(..., description="Clear explanation")
```

Every schema MUST have examples:
```python
model_config = {"json_schema_extra": {"examples": [...]}}
```

**Pattern to follow**: `/backend/app/schemas/setup.py`

### Verification

After any API change:
1. Visit `http://localhost:8000/docs` - verify Swagger UI shows changes
2. Visit `http://localhost:8000/redoc` - verify ReDoc renders correctly

---

## Git Workflow (MANDATORY)

```bash
# 1. Create feature branch
git checkout -b feature/descriptive-name

# 2. Run ALL tests before committing (see docs/guides/testing.md)

# 3. Commit
git add . && git commit -m "type: description"

# 4. Push and create PR
git push -u origin feature/descriptive-name
gh pr create --title "Title" --body "Description"
```

**NEVER**: Push directly to main, skip tests, mark complete without PR.

---

## Bug Fixing Rules

- ❌ NEVER use fake data to make tests pass
- ❌ NEVER add workarounds instead of fixing root cause
- ✅ Investigate deeply with logging
- ✅ Test with different inputs
- ✅ Delegate complex issues to specialized agents

---

## Code Patterns

When writing service or repository code, read `docs/guides/engineering-standards.md` section 6.

---

## Completion Checklist

- [ ] Backend tests: 100% passing
- [ ] Coverage: >= 80%
- [ ] Smoke tests: passing
- [ ] Feature branch: created
- [ ] PR: created
- [ ] API documentation: updated (if API changes made)
- [ ] Swagger UI verified (if API changes made)
- [ ] URL paths use kebab-case (if new endpoints added)
- [ ] Pagination uses `items` key with standard structure (if paginated endpoints)

---

## Quick Commands

When starting services, read `docs/guides/development.md`.
When running tests, read `docs/guides/testing.md`.

---

## Database Migrations (Alembic)

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

**Docker** (use `./scripts/dc.sh`):
```bash
./scripts/dc.sh exec backend-dev alembic upgrade head
./scripts/dc.sh exec backend-dev alembic current
```

**Best Practices**:
- Always review auto-generated migrations before applying
- Test rollbacks: `upgrade head` → `downgrade -1` → `upgrade head`
- Descriptive names: `add_index_to_patterns_symbol` not `update`

**Troubleshooting**:
- "Can't locate revision" → `alembic stamp head`
- "Not up to date" → `alembic upgrade head`
