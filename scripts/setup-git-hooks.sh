#!/bin/bash
# Setup Git Hooks for Trading Analyst
#
# This script installs git hooks from scripts/hooks/ to .git/hooks/
# Run this after cloning the repository or pulling hook updates.

set -e

echo "🔧 Setting up Git hooks..."

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_SOURCE="$REPO_ROOT/scripts/hooks"
HOOKS_DEST="$REPO_ROOT/.git/hooks"

# Check if .git directory exists
if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "❌ Error: .git directory not found"
  echo "   Make sure you're running this from the repository root"
  exit 1
fi

# Check if hooks source directory exists
if [ ! -d "$HOOKS_SOURCE" ]; then
  echo "❌ Error: scripts/hooks directory not found"
  exit 1
fi

# Install each hook
installed_count=0
for hook in "$HOOKS_SOURCE"/*; do
  if [ -f "$hook" ]; then
    hook_name=$(basename "$hook")

    # Skip README or other documentation files
    if [[ "$hook_name" == "README.md" ]]; then
      continue
    fi

    echo "  📦 Installing $hook_name..."
    cp "$hook" "$HOOKS_DEST/$hook_name"
    chmod +x "$HOOKS_DEST/$hook_name"
    installed_count=$((installed_count + 1))
  fi
done

echo ""
if [ $installed_count -eq 0 ]; then
  echo "⚠️  No hooks found to install"
else
  echo "✅ Successfully installed $installed_count git hook(s)"
  echo ""
  echo "Installed hooks:"
  ls -lh "$HOOKS_DEST" | grep -E '^-rwx' | awk '{print "  •", $9}'
fi

echo ""
echo "💡 Tip: Run this script again after pulling hook updates"
