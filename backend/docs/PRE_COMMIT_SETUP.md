# Pre-commit Hooks Setup

## Overview

Pre-commit hooks automatically enforce code quality standards before commits. This prevents non-compliant code from entering the repository.

## Prerequisites

Pre-commit hooks run on the **host machine**, not inside Docker, because they need to intercept git commit operations.

## Installation

### 1. Install pre-commit on your host machine

```bash
# macOS
brew install pre-commit

# Or via pip
pip install pre-commit

# Or via pipx (recommended for tools)
pipx install pre-commit
```

### 2. Install git hooks

From the backend directory:

```bash
cd backend
pre-commit install
```

This creates git hooks that run automatically on `git commit`.

## Usage

### Automatic (Recommended)

Hooks run automatically when you commit:

```bash
git commit -m "your message"
```

If hooks fail, the commit is blocked. Fix the issues and retry.

### Manual

Run hooks on all files:

```bash
cd backend
pre-commit run --all-files
```

Run specific hook:

```bash
pre-commit run black --all-files
pre-commit run ruff --all-files
```

### Bypass (Emergency Only)

To commit without running hooks (use sparingly):

```bash
git commit --no-verify -m "emergency fix"
```

## Configured Hooks

1. **trailing-whitespace**: Remove trailing whitespace
2. **end-of-file-fixer**: Ensure files end with newline
3. **check-yaml**: Validate YAML syntax
4. **check-json**: Validate JSON syntax
5. **check-toml**: Validate TOML syntax
6. **check-added-large-files**: Prevent committing large files (>1MB)
7. **check-merge-conflict**: Detect merge conflict markers
8. **black**: Format Python code (100 char line length)
9. **isort**: Sort imports
10. **ruff**: Lint Python code (with auto-fix)

## Configuration

See `.pre-commit-config.yaml` for configuration details.

### Customization

To ignore certain Ruff rules:

```yaml
- id: ruff
  args:
    - --fix
    - --ignore=D200,D415  # Ignore specific rules
```

To update hook versions:

```bash
pre-commit autoupdate
```

## Docker Considerations

**Important**: Pre-commit hooks run on the host, using host Python environment. They are **not** run inside Docker containers.

If you prefer running tools inside Docker:

```bash
# Black
./scripts/dc.sh exec backend-dev black app/ tests/

# Ruff
./scripts/dc.sh exec backend-dev python -m ruff check --fix app/ tests/

# isort (via Ruff)
# Ruff's isort integration handles import sorting
```

## Troubleshooting

### Hooks fail with "command not found"

Ensure pre-commit is installed on your host machine, not just in Docker.

### Hooks are slow

First run downloads hook environments. Subsequent runs are fast (cached).

### Want to skip a specific hook

```bash
SKIP=black git commit -m "message"
```

### Update hook versions

```bash
cd backend
pre-commit autoupdate
git add .pre-commit-config.yaml
git commit -m "Update pre-commit hooks"
```

## CI/CD Integration

To run pre-commit in CI:

```yaml
# .github/workflows/ci.yml
- name: Run pre-commit
  run: |
    pip install pre-commit
    pre-commit run --all-files
```

## Best Practices

1. **Install early**: Set up pre-commit at project start
2. **Update regularly**: Run `pre-commit autoupdate` monthly
3. **Don't bypass**: Use `--no-verify` only for emergencies
4. **Fix, don't skip**: Address failures rather than skipping hooks
5. **Team alignment**: Ensure all developers have pre-commit installed