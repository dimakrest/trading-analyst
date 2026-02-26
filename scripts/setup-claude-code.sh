#!/bin/bash
# Setup Claude Code with plugins and skills for this project
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Claude Code Setup Script ==="
echo ""

# 1. Check Claude Code installation
echo "Checking Claude Code installation..."
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Claude Code is not installed.${NC}"
    echo ""
    echo "Please install Claude Code first:"
    echo "  macOS (Homebrew): brew install claude-code"
    echo "  npm:              npm install -g @anthropic-ai/claude-code"
    echo "  Direct download:  https://claude.ai/code"
    echo ""
    exit 1
fi

CLAUDE_VERSION=$(claude --version 2>/dev/null || echo "unknown")
echo -e "${GREEN}✓ Claude Code installed: $CLAUDE_VERSION${NC}"
echo ""

# 2. Add official plugins marketplace
echo "Adding official plugins marketplace..."
claude plugin marketplace add anthropics/claude-plugins-official 2>/dev/null || true
echo -e "${GREEN}✓ Marketplace configured${NC}"
echo ""

# 3. Install skills/plugins
echo "Installing plugins..."
claude plugin install frontend-design@claude-plugins-official || true
claude plugin install code-simplifier@claude-plugins-official || true
echo -e "${GREEN}✓ Skills installed: frontend-design, code-simplifier${NC}"
echo ""

# 4. Install LSP plugins
echo "Installing LSP plugins..."
claude plugin install pyright-lsp@claude-plugins-official || true
claude plugin install typescript-lsp@claude-plugins-official || true
echo -e "${GREEN}✓ LSP plugins installed: pyright-lsp, typescript-lsp${NC}"
echo ""

# 5. Check language server dependencies
echo "=== Language Server Status ==="
echo ""

MISSING_SERVERS=()

# Check Pyright (Python)
echo "Checking Pyright (Python LSP)..."
if command -v pyright &> /dev/null || command -v pyright-langserver &> /dev/null; then
    echo -e "${GREEN}✓ Pyright is installed${NC}"
else
    echo -e "${YELLOW}⚠ Pyright not found${NC}"
    MISSING_SERVERS+=("pyright")
fi

# Check TypeScript Language Server
echo "Checking TypeScript Language Server..."
if command -v typescript-language-server &> /dev/null; then
    echo -e "${GREEN}✓ TypeScript Language Server is installed${NC}"
else
    echo -e "${YELLOW}⚠ TypeScript Language Server not found${NC}"
    MISSING_SERVERS+=("typescript")
fi

echo ""

# Display installation instructions for missing servers
if [ ${#MISSING_SERVERS[@]} -gt 0 ]; then
    echo -e "${YELLOW}=== Action Required ===${NC}"
    echo "Some language servers need to be installed for LSP features to work:"
    echo ""

    for server in "${MISSING_SERVERS[@]}"; do
        case $server in
            "pyright")
                echo "Python (Pyright):"
                echo "  pip install pyright"
                echo "  OR"
                echo "  npm install -g pyright"
                echo ""
                ;;
            "typescript")
                echo "TypeScript:"
                echo "  npm install -g typescript-language-server typescript"
                echo ""
                ;;
        esac
    done

    echo "After installing, restart Claude Code for LSP features to activate."
else
    echo -e "${GREEN}=== Setup Complete ===${NC}"
    echo "All language servers are installed. LSP features should work."
fi

echo ""
echo "Installed plugins:"
echo "  - frontend-design: Use /frontend-design for UI work"
echo "  - code-simplifier: Use Task tool with code-simplifier agent"
echo "  - pyright-lsp: Python code intelligence"
echo "  - typescript-lsp: TypeScript/React code intelligence"
