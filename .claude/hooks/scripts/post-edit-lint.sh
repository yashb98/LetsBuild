#!/usr/bin/env bash
# PostToolUse hook: auto-lint after every file edit
# Fires on Write and Edit tool calls

FILE_PATH="$1"

# Only lint Python files
if [[ "$FILE_PATH" == *.py ]]; then
    ruff check "$FILE_PATH" --fix --quiet 2>/dev/null
    ruff format "$FILE_PATH" --quiet 2>/dev/null
fi

# Only lint TypeScript/JavaScript files
if [[ "$FILE_PATH" == *.ts ]] || [[ "$FILE_PATH" == *.tsx ]] || [[ "$FILE_PATH" == *.js ]] || [[ "$FILE_PATH" == *.jsx ]]; then
    if command -v npx &> /dev/null; then
        npx --yes prettier --write "$FILE_PATH" --log-level silent 2>/dev/null
    fi
fi

exit 0
