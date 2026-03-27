# Rules: Agent Code (letsbuild/forge/**/*)

## Agentic Loop Pattern

Every agent in Code Forge MUST implement the canonical stop_reason loop:

1. Send request with tools + system prompt
2. Check `response.stop_reason`
3. If `"tool_use"` → execute tool, append result, loop
4. If `"end_turn"` → extract final output, exit

NEVER use iteration caps as the primary stop condition. A safety cap of 50 turns is acceptable as a fallback but MUST NOT be the design intent.

## Tool Scoping

Each agent gets ≤5 tools. Enforce via `allowed_tools` list in agent config:

- **Planner:** `read_file`, `list_directory` (read-only sandbox)
- **Coder:** `write_file`, `bash_execute`, `install_package`, `read_file`
- **Tester:** `read_file`, `bash_execute`, `write_file`
- **Reviewer:** `read_file`, `list_directory` (read-only, ZERO coder context)
- **Integrator:** `read_file`, `write_file`, `bash_execute`, `docker_build`

If you need a new tool for an agent, justify why it cannot be accomplished with existing tools.

## Independent Review

The Reviewer agent MUST use a fresh `anthropic.Anthropic()` client call with:
- No prior conversation history from the Coder
- Only: generated code + ProjectSpec + quality checklist
- Its own system prompt focused on critique, not generation

## Retry-With-Feedback

When Tester detects failures:
1. Capture exact error output + failing assertion + relevant code
2. Append structured error context to Coder's next prompt
3. Coder generates targeted fix, not full re-generation
4. Max 3 retries per task. After that, flag for human review.

## Agent Base Class

All agents inherit from `BaseAgent` in `letsbuild/forge/base_agent.py`. Override:
- `system_prompt() -> str`
- `tools() -> list[dict]`
- `process_result(response) -> AgentOutput`

## Error Handling

Every tool execution MUST return structured errors:
```python
StructuredError(
    error_category="transient" | "validation" | "business" | "permission",
    is_retryable=True | False,
    partial_results=...,
    attempted_query=...
)
```
