# Git Hooks

This directory contains git hooks for the Trading Analyst project.

## Installation

Run the setup script from the repository root:

```bash
./scripts/setup-git-hooks.sh
```

This will copy all hooks from `scripts/hooks/` to `.git/hooks/` and make them executable.

## Available Hooks

### pre-commit

**Purpose**: Enforce WCAG AA color contrast compliance before allowing commits.

**What it checks**:
- ❌ **Forbidden patterns** (blocks commit):
  - `dark:` classes (e.g., `dark:text-white`)
  - Low-contrast colors: `text-red-500`, `text-green-500`, `text-green-600`
  - Inline color styles: `style={{ color: '#xxx' }}`

- ⚠️  **Warning patterns** (allows commit with warning):
  - Hardcoded gray colors: `text-gray-600`, `bg-gray-100`
  - Suggests ShadCN semantic color alternatives

**Files checked**: Staged `.tsx`, `.ts`, `.css` files only

**Bypass** (emergency only):
```bash
git commit --no-verify
```

## For New Developers

After cloning the repository:

1. Run the setup script:
   ```bash
   ./scripts/setup-git-hooks.sh
   ```

2. Verify installation:
   ```bash
   ls -la .git/hooks/pre-commit
   # Should show: -rwxr-xr-x (executable)
   ```

3. Test the hook:
   ```bash
   # Try committing a file with a violation
   echo 'className="text-green-600"' > test.tsx
   git add test.tsx
   git commit -m "test"
   # Expected: Hook blocks the commit
   rm test.tsx
   git reset HEAD
   ```

## Updating Hooks

When hooks are updated in `scripts/hooks/`:

1. Pull the latest changes:
   ```bash
   git pull
   ```

2. Re-run the setup script:
   ```bash
   ./scripts/setup-git-hooks.sh
   ```

## Why Not Use Husky?

This project uses a simple shell script approach instead of Husky because:
- **Simplicity**: No additional npm dependencies
- **Transparency**: Hook code is visible and easy to understand
- **Control**: Direct bash scripts, no abstraction layer
- **Lightweight**: Single setup script, no package.json modifications

For larger teams or more complex hook requirements, consider migrating to Husky.

## References

- Pre-commit hook implementation: `scripts/hooks/pre-commit`
- Design system (colors, accessibility, styling): `docs/frontend/DESIGN_SYSTEM.md`
