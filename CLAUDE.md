# LetsBuild — Autonomous Portfolio Factory

> JD → Research → Design → Sandbox Code → GitHub → Content. Fully autonomous.

## What This Is

LetsBuild is an open-source 10-layer agentic pipeline that ingests job descriptions and produces production-ready, company-tailored GitHub repositories with realistic commit histories, ADRs, CI/CD, tutorials, and content. It combines DeerFlow infrastructure patterns, Claude Certified Architect exam patterns, and Ruflo intelligence patterns (23 total).

## Architecture (10 Layers)

| Layer | Name | Module Path |
|-------|------|-------------|
| L0 | Agent Harness + Guidance Control Plane | `letsbuild/harness/` |
| L1 | Intake Engine | `letsbuild/intake/` |
| L2 | Company Intelligence | `letsbuild/intelligence/` |
| L3 | Match & Score Engine | `letsbuild/matcher/` |
| L4 | Project Architect | `letsbuild/architect/` |
| L5 | Code Forge | `letsbuild/forge/` |
| L6 | GitHub Publisher | `letsbuild/publisher/` |
| L7 | Content Factory | `letsbuild/content/` |
| L8 | Memory + ReasoningBank | `letsbuild/memory/` |
| L9 | Agent Hooks + Enforcement | `letsbuild/hooks/` |

Cross-cutting: `letsbuild/gateway/` (MCP + messaging), `letsbuild/models/` (Pydantic schemas), `letsbuild/pipeline/` (orchestrator), `skills/` (project templates)

## Tech Stack

- **Language:** Python 3.12, strict typing with `mypy --strict`
- **Framework:** Typer (CLI), FastAPI (API + MCP), Next.js 15 (web dashboard)
- **AI:** Anthropic SDK (`anthropic` package), tool_use for all structured output
- **Async:** `asyncio` + `httpx` for all I/O-bound operations
- **Validation:** Pydantic v2 for every data boundary
- **Storage:** SQLite + HNSW (hnswlib) for ReasoningBank, Redis for pipeline state
- **Containers:** Docker SDK for Python (`docker` package) for sandbox management
- **Testing:** `pytest` + `pytest-asyncio`, target 80%+ coverage
- **Linting:** `ruff check .` and `ruff format .`
- **Type checking:** `mypy --strict letsbuild/`

## Build & Test Commands

```bash
# Install
pip install -e ".[dev]" --break-system-packages

# Run tests (single file preferred for speed)
pytest tests/path/to/test_file.py -v

# Full test suite
pytest tests/ -v --cov=letsbuild --cov-report=term-missing

# Lint + format
ruff check . --fix && ruff format .

# Type check
mypy --strict letsbuild/

# Run CLI
python -m letsbuild.cli ingest --url <jd_url>
python -m letsbuild.cli run --file <jd_path>

# Docker sandbox build
docker build -t letsbuild/sandbox:latest -f sandbox/Dockerfile .
```

## Critical Coding Patterns

### 1. Agentic Loops — stop_reason based (NEVER iteration caps)
```python
while True:
    response = client.messages.create(model=model, messages=messages, tools=tools)
    if response.stop_reason == "tool_use":
        tool_results = execute_tools(response)
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    elif response.stop_reason == "end_turn":
        break  # Agent decided it is done
```

### 2. Structured Output — tool_use with JSON schemas (NEVER parse free text)
```python
response = client.messages.create(
    tool_choice={"type": "tool", "name": "extract_jd_analysis"},
    tools=[jd_analysis_tool_schema],
    ...
)
```

### 3. Scoped Tools — each agent gets ≤5 tools, no cross-specialisation

### 4. Independent Review — Reviewer has ZERO prior context from Coder

### 5. Structured Errors — every tool returns `errorCategory` + `isRetryable` on failure

### 6. PostToolUse Trimming — hooks trim verbose tool output before context accumulates

### 7. Policy Gates — PublishGate, SecurityGate, QualityGate, BudgetGate are deterministic code, not prompts

## File Conventions

- One class per file for agents, middleware, hooks, gates
- Pydantic models in `letsbuild/models/` grouped by layer (e.g., `intake_models.py`, `forge_models.py`)
- Skill files in `skills/` with `.skill.md` extension and YAML frontmatter
- Tests mirror source: `tests/harness/test_middleware.py` ↔ `letsbuild/harness/middleware.py`
- All async functions use `async def`, never `threading`

## Git Conventions

- Branch: `feat/<layer>-<description>`, `fix/<layer>-<description>`, `test/<layer>-<description>`
- Commits: Conventional Commits — `feat(intake):`, `fix(forge):`, `test(matcher):`, `docs:`, `chore:`
- PR: one layer per PR when possible

## What NOT To Do

- NEVER use arbitrary iteration caps as the primary stopping mechanism for agents
- NEVER give an agent tools outside its specialisation
- NEVER let the LLM enforce business rules that must be 100% reliable — use gates/hooks
- NEVER parse free-text LLM output for structured data — use tool_use
- NEVER let the Reviewer share context with the Coder
- NEVER store secrets in code — trufflehog runs in PrePublish hook
- NEVER skip sandbox validation before publishing

## Path-Scoped Rules

See `.claude/rules/` for context-specific rules:
- `agents.md` → scoped to `letsbuild/forge/**/*`
- `testing.md` → scoped to `tests/**/*`
- `skills.md` → scoped to `skills/**/*`
- `pipeline.md` → scoped to `letsbuild/pipeline/**/*`, `letsbuild/harness/**/*`
- `models.md` → scoped to `letsbuild/models/**/*`
- `security.md` → scoped to `letsbuild/hooks/**/*`, `letsbuild/publisher/**/*`

## Key References

- @docs/architecture/ARCHITECTURE.md for full 10-layer specification
- @docs/architecture/DATA_FLOW.md for pipeline data flow
- @docs/contributing/SKILL_AUTHORING.md for writing new skills
- @README.md for project overview
- @pyproject.toml for dependencies and scripts
