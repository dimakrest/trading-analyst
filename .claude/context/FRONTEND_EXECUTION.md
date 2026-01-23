# Frontend Execution Agent Instructions

**For**: frontend-engineer, frontend implementation

## Task Completion Definition

A task is ONLY complete when ALL are true:
- ✅ Unit tests passing (100%)
- ✅ E2E tests passing (100%)
- ✅ Coverage >= 80%
- ✅ TypeScript: 0 errors
- ✅ Feature branch + PR created
- ✅ No known bugs

**NEVER** mark complete with failing tests or < 80% coverage.

---

## Testing Requirements

When running tests, read `docs/guides/testing.md`.

**E2E tests are NOT optional** - 100% pass rate required.

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

**NEVER**: Push directly to main, skip E2E tests, accept < 100% pass rate.

---

## Bug Fixing Rules

- ❌ NEVER use mock data to make E2E tests pass
- ❌ NEVER accept partial pass rates (43%, 80%, 95%)
- ✅ Investigate with DevTools and React DevTools
- ✅ Test different inputs and edge cases
- ✅ Delegate complex issues to specialized agents

---

## Design System

**MANDATORY**: Follow `docs/frontend/DESIGN_SYSTEM.md` for all styling decisions.

**Key rules**:
- Use semantic color tokens, never hardcoded Tailwind colors
- `text-accent-bullish`/`text-accent-bearish` for P&L values
- `text-signal-long`/`text-signal-short` for screener signals
- `text-up-indicator`/`text-down-indicator` for technical indicators
- `font-mono` for all numeric values
- `font-display` for headers and symbols

**Forbidden patterns** (pre-commit hook blocks these):
```tsx
// ❌ BLOCKED - hardcoded colors
<span className="text-green-500">+$100</span>
<span className="text-red-500">-$50</span>

// ✅ CORRECT - semantic tokens
<span className="text-accent-bullish">+$100</span>
<span className="text-accent-bearish">-$50</span>
```

---

## Code Patterns

When writing components or hooks, read `docs/guides/engineering-standards.md` section 6.

---

## API Conventions

When calling backend APIs, read `docs/guides/engineering-standards.md` section 8.

---

## Completion Checklist

- [ ] Unit tests: 100% passing
- [ ] E2E tests: 100% passing
- [ ] Coverage: >= 80%
- [ ] TypeScript: 0 errors
- [ ] Smoke tests: passing
- [ ] Feature branch + PR: created

---

## Process Management

**Before starting dev server**:
```bash
lsof -ti:5174 | xargs kill -9 2>/dev/null
cd frontend && npm run dev
```

**Cleanup after task**:
```bash
pkill -f vitest
```
