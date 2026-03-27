#!/usr/bin/env bash
# PreToolUse hook: guard dangerous bash commands
# Blocks destructive operations that could harm the host system

COMMAND="$1"

# Block dangerous patterns
BLOCKED_PATTERNS=(
    "rm -rf /"
    "rm -rf ~"
    "rm -rf \$HOME"
    "mkfs"
    "dd if="
    ":(){:|:&};:"
    "chmod -R 777 /"
    "curl.*|.*bash"
    "wget.*|.*bash"
    "pip install --break-system-packages" # only allow in controlled contexts
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qE "$pattern"; then
        echo "BLOCKED: Dangerous command pattern detected: $pattern" >&2
        exit 1
    fi
done

# Block writes to protected directories
PROTECTED_DIRS=("/etc" "/usr" "/var" "/boot" "/sys" "/proc")
for dir in "${PROTECTED_DIRS[@]}"; do
    if echo "$COMMAND" | grep -qE "(>|>>|tee|mv|cp|rm).*$dir"; then
        echo "BLOCKED: Write to protected directory: $dir" >&2
        exit 1
    fi
done

exit 0
