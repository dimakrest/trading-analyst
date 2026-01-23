# Testing Guide

This is the **single source of truth** for all testing in the project.

---

## Prerequisites

Start development services before running any tests:

```bash
./scripts/dc.sh up -d  # Start all services
```

---

## Quick Reference

```bash
# Backend - run all tests with coverage
./scripts/dc.sh exec backend-dev pytest -v --cov=app --cov-report=term-missing

# Frontend - all tests
cd frontend && npm run test:all
```

---

## Backend Tests

**Run inside Docker container using the wrapper script:**

```bash
# Run all tests with coverage
./scripts/dc.sh exec backend-dev pytest --cov=app --cov-report=term-missing

# Run specific test file
./scripts/dc.sh exec backend-dev pytest tests/specific_test.py -v

# Run tests by pattern
./scripts/dc.sh exec backend-dev pytest -k "pattern_name" -v

# Run by marker
./scripts/dc.sh exec backend-dev pytest -m unit
./scripts/dc.sh exec backend-dev pytest -m integration
./scripts/dc.sh exec backend-dev pytest -m slow
./scripts/dc.sh exec backend-dev pytest -m database

# HTML coverage report (view backend/htmlcov/index.html)
./scripts/dc.sh exec backend-dev pytest --cov=app --cov-report=html
```

**Requirements**: 100% pass rate, >= 80% coverage

---

## Frontend Tests

**Test Types:**

| Type | Command | Description |
|------|---------|-------------|
| Unit | `npm run test:unit` | Vitest - component and hook tests |
| UI (mocked) | `npm run test:ui` | Playwright - UI tests with mocked backend |
| E2E (real backend) | `npm run test:e2e` | Playwright - full integration with real backend |
| All tests | `npm run test:all` | Runs unit, UI, and E2E tests |
| Coverage | `npm run test:coverage` | Unit tests with coverage report |
| TypeScript | `npm run type-check` | Type checking (0 errors required) |

```bash
# Run from frontend directory
cd frontend

# Unit tests
npm run test:unit           # Run once
npm run test:unit -- --watch # Watch mode

# Coverage (view frontend/coverage/index.html)
npm run test:coverage

# UI tests (mocked backend)
npm run test:ui

# E2E tests (requires backend running)
npm run test:e2e            # Headless
npm run test:e2e:headed     # See browser

# All tests
npm run test:all

# TypeScript
npm run type-check
```

**Requirements**: 100% pass rate for all test types, >= 80% coverage

**E2E tests are NOT optional** - they must pass before any frontend task is complete.

---

## Test Structure

**Backend** (`backend/tests/`):
- `unit/services/` - Service logic tests
- `unit/models/` - Model tests
- `integration/` - API integration tests

**Frontend**:
- `src/**/*.test.tsx` - Colocated unit tests with components
- `tests/ui/` - Mocked UI tests (Playwright)
- `tests/e2e/` - Real backend E2E tests (Playwright)

---

## Testing Standards

### AAA Pattern (Required)

All tests must follow Arrange/Act/Assert:

```python
# Backend example
async def test_create_simulation(service):
    # Arrange
    params = {"ticker": "AAPL"}

    # Act
    result = await service.create(params)

    # Assert
    assert result.ticker == "AAPL"
```

```typescript
// Frontend example
it('should submit the form', async () => {
  // Arrange
  render(<SetupForm />);

  // Act
  await userEvent.click(screen.getByRole('button', { name: /submit/i }));

  // Assert
  expect(mockSubmit).toHaveBeenCalled();
});
```

### Accessible Queries (Required)

Use role-based queries, not test IDs:

```typescript
// ✅ Use role-based queries
screen.getByRole('button', { name: /submit/i })
screen.getByLabelText(/ticker/i)
screen.getByRole('heading', { name: /dashboard/i })

// ❌ Avoid test IDs
screen.getByTestId('submit-button')
```

---

## Coverage Requirements

| Type | Target | Pass Rate |
|------|--------|-----------|
| Backend | >= 80% | 100% |
| Frontend | >= 80% | 100% |
| E2E | N/A | 100% |

**Coverage check is manual**: Always check output shows >= 80%.

---

## E2E Test Execution Rules

**NEVER use `tail` or output truncation when running E2E tests**

- E2E tests can take a long time and produce important output
- Always capture full output: `npm run test:e2e 2>&1`
- Never truncate with `| tail -N` or `| head -N`
- Wait for tests to complete fully before checking results

---

## Before Marking Task Complete

- [ ] All tests pass (100%)
- [ ] Coverage >= 80%
- [ ] TypeScript: 0 errors
