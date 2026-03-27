# Rules: Test Code (tests/**/*)

## Test Structure

Tests mirror the source tree:
- `tests/harness/` → `letsbuild/harness/`
- `tests/intake/` → `letsbuild/intake/`
- `tests/forge/` → `letsbuild/forge/`
- etc.

Each test file: `test_<module_name>.py`

## Naming Convention

```python
def test_<what>_<condition>_<expected>():
    """Descriptive docstring explaining the scenario."""
```

Example: `test_intake_engine_missing_skills_returns_empty_list()`

## Async Tests

Use `pytest-asyncio` with `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_company_research_timeout_returns_structured_error():
    ...
```

## Fixtures

- Shared fixtures in `tests/conftest.py`
- Layer-specific fixtures in `tests/<layer>/conftest.py`
- ALWAYS use fixtures for: Anthropic client mocks, sandbox instances, sample JDs, sample CompanyProfiles

## Mocking the Anthropic API

NEVER call the real Anthropic API in tests. Mock at the `client.messages.create` level:
```python
@pytest.fixture
def mock_anthropic(monkeypatch):
    mock_response = MockResponse(stop_reason="end_turn", content=[...])
    monkeypatch.setattr("anthropic.Anthropic.messages.create", lambda **kw: mock_response)
```

## Coverage Requirements

- Target: 80%+ overall, 90%+ for models/ and harness/
- Every gate (PublishGate, SecurityGate, QualityGate, BudgetGate) must have explicit pass AND fail tests
- Every middleware must have before() and after() tests
- Every agent must have: normal completion test, tool_use loop test, error handling test

## What to Test in Each Layer

| Layer | Must Test |
|-------|-----------|
| L0 Harness | Middleware chain order, gate enforcement, sandbox lifecycle |
| L1 Intake | JD parsing accuracy, structured output validation, edge cases (empty JD, non-English) |
| L2 Intelligence | Sub-agent timeout handling, structured errors, cache hit/miss, partial results merge |
| L3 Matcher | Score calculation, gap categorisation, edge cases (perfect match, zero match) |
| L4 Architect | Skill selection, ProjectSpec completeness, ADR generation |
| L5 Forge | stop_reason loop, tool scoping enforcement, retry-with-feedback, independent review isolation |
| L6 Publisher | Commit strategy, README rendering, security scan integration |
| L7 Content | Template rendering, format correctness |
| L8 Memory | ReasoningBank CRUD, HNSW retrieval accuracy, JUDGE verdict recording, DISTILL pattern extraction |
| L9 Hooks | Hook firing order, PreToolUse blocking, PostToolUse trimming |
