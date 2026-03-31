# Rules: Arena Code (letsbuild/arena/**/* , tests/arena/**/*)

## Reuse — Do NOT Reimplement

- Agents extend `letsbuild.forge.base_agent.BaseAgent`
- Sandbox ops use `letsbuild.harness.sandbox.SandboxManager`
- Parallel execution uses `letsbuild.forge.executor.ForgeExecutor`
- State pattern follows `letsbuild.pipeline.state.PipelineState`
- Middleware pattern follows `letsbuild.harness.middleware.MiddlewareChain`
- Error model uses `letsbuild.models.shared.StructuredError`
- NEVER modify files in `letsbuild/forge/`, `letsbuild/harness/`, `letsbuild/pipeline/`

## Patterns

- `async def` for all I/O
- `structlog.get_logger()` for logging
- Pydantic v2 with `ConfigDict(strict=True)` for all models
- `tool_use` for structured LLM output — NEVER parse free text
- Agents scoped to ≤5 tools
- Agent loops: `stop_reason` based — NEVER iteration caps as primary stop
- Scoring: deterministic code, NOT LLM decisions
- Cross-review: reviewer has ZERO context from the building team

## Test Pattern

Tests mirror source: `tests/arena/test_<module>.py` ↔ `letsbuild/arena/<module>.py`
Use `respx` for HTTP mocks. Use `pytest-asyncio`. Mock LLM with tool_use responses.

## Git

Commits: `feat(arena): <description>` or `test(arena): <description>`
