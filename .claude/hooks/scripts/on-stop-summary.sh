#!/usr/bin/env bash
# Stop hook: print a session summary when Claude Code finishes a turn
# Helps track what was accomplished and what's next

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Session checkpoint"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Count modified files
if command -v git &> /dev/null && git rev-parse --is-inside-work-tree &> /dev/null; then
    MODIFIED=$(git diff --name-only 2>/dev/null | wc -l)
    STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l)
    UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l)
    echo "  Modified: $MODIFIED | Staged: $STAGED | New: $UNTRACKED"
fi

# Check test status (quick — only if pytest is available)
if command -v pytest &> /dev/null; then
    TEST_COUNT=$(find tests/ -name "test_*.py" 2>/dev/null | wc -l)
    echo "  Test files: $TEST_COUNT"
fi

# Check lint status
if command -v ruff &> /dev/null; then
    LINT_ERRORS=$(ruff check letsbuild/ 2>/dev/null | tail -1)
    echo "  Lint: $LINT_ERRORS"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exit 0
