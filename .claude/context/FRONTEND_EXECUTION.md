# Frontend Execution Agent Instructions

**For**: frontend-engineer, frontend implementation

## Task Completion Definition

A task is ONLY complete when ALL are true:
- Unit tests passing (100%)
- E2E tests passing (100%) - if applicable
- Coverage >= 80% (adjust per project)
- TypeScript: 0 errors
- Feature branch + PR created
- No known bugs

**NEVER** mark complete with failing tests or type errors.

---

## Testing Requirements

Check your project's testing documentation for specific commands.

**E2E tests are NOT optional** - 100% pass rate required (if applicable).

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

**NEVER**: Push directly to main, skip E2E tests, accept < 100% pass rate.

---

## Bug Fixing Rules

- NEVER use mock data to make E2E tests pass
- NEVER accept partial pass rates (43%, 80%, 95%)
- Investigate with DevTools and React DevTools
- Test different inputs and edge cases
- Delegate complex issues to specialized agents

---

## Design System (if applicable)

If your project has a design system:
- Use semantic color tokens, never hardcoded colors
- Use proper font families for different contexts
- Follow the project's design documentation

---

## Code Patterns

Follow your project's engineering standards documentation for:
- Component patterns
- Hook patterns
- State management patterns

---

## Completion Checklist

- [ ] Unit tests: 100% passing
- [ ] E2E tests: 100% passing (if applicable)
- [ ] Coverage: >= threshold
- [ ] TypeScript: 0 errors
- [ ] Feature branch + PR: created

---

## Process Management

**Before starting dev server**:
```bash
# Kill any existing process on dev port
lsof -ti:5173 | xargs kill -9 2>/dev/null
npm run dev
```

**Cleanup after task**:
```bash
pkill -f vitest
```
