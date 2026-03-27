# Contributing to LetsBuild

Thank you for your interest in contributing! LetsBuild is built to be community-driven.

## Development Setup

```bash
git clone https://github.com/yashb98/LetsBuild.git
cd LetsBuild
pip install -e ".[dev]"
pre-commit install
```

## Contribution Pathways

### 1. Project Skills (most wanted)
New project type templates for categories we don't cover yet. See [Skill Authoring Guide](docs/contributing/SKILL_AUTHORING.md).

### 2. Code Gen Skills
Language/framework-specific code generation patterns (e.g., `rust-axum.skill.md`, `go-gin.skill.md`).

### 3. Research Plugins
Industry-specific data sources for Company Intelligence (Layer 2).

### 4. Quality Benchmarks
New test JDs with expected quality scores for the benchmark suite.

### 5. Bug Fixes & Improvements
Check the [Issues](https://github.com/yashb98/LetsBuild/issues) page.

## Workflow

1. Fork the repo
2. Create a branch: `feat/<layer>-<description>` or `fix/<layer>-<description>`
3. Make your changes
4. Run: `make ci` (lint + typecheck + test)
5. Commit with Conventional Commits: `feat(intake): add PDF JD parsing`
6. Open a PR against `main`

## Code Standards

- Python 3.12, strict typing with `mypy --strict`
- Pydantic v2 for all data models
- `ruff` for linting and formatting
- `pytest` with 80%+ coverage target
- Async-first (`async def`, `httpx`, `asyncio`)

## Claude Code Users

This repo ships with a complete `.claude/` directory. When working on LetsBuild with Claude Code, it automatically picks up the coding standards, architecture patterns, and testing conventions.

## Architecture Rules

- Every agent uses stop_reason-based loops, never iteration caps
- Each agent has ≤5 scoped tools
- Business rules use gates/hooks, never prompt instructions
- All structured data uses tool_use with JSON schemas
- The Reviewer agent has zero context from the Coder

See [CLAUDE.md](CLAUDE.md) for the complete coding patterns reference.
