# AgentForge Arena — Build Plan

> Drop this + the `arena-context/` folder into LetsBuild repo root.
> Then: `claude` → "Read ARENA_BUILD_PLAN.md and start Phase A"

## What This Is

Competitive tournament module where AI agent teams compete to build apps.
Integrates INTO LetsBuild — reuses BaseAgent, SandboxManager, ForgeExecutor.
~3,500 new LOC across 8 phases.

## Phases (execute in order)

| Phase | What | Context File | Est. LOC |
|-------|------|-------------|----------|
| A | Models + Foundation | `arena-context/tasks/phase-a-models.md` | 400 |
| B | Arena Agents | `arena-context/tasks/phase-b-agents.md` | 600 |
| C | Scoring + Judging | `arena-context/tasks/phase-c-scoring.md` | 400 |
| D | Spectator + Streaming | `arena-context/tasks/phase-d-spectator.md` | 350 |
| E | Challenges Library | `arena-context/tasks/phase-e-challenges.md` | 400 |
| F | Tournament Controller | `arena-context/tasks/phase-f-controller.md` | 500 |
| G | CLI + Gateway | `arena-context/tasks/phase-g-cli-gateway.md` | 350 |
| H | Config + Docs | `arena-context/tasks/phase-h-config-docs.md` | 200 |

## How to Use

For each phase, tell Claude Code:
```
Read arena-context/tasks/phase-X-<name>.md and build it.
```

Or use the slash commands (after placing files in `.claude/commands/`):
```
/arena-build-phase-a
/arena-build-phase-b
...
```

## Rules (auto-loaded)

Copy `arena-context/rules/arena.md` → `.claude/rules/arena.md`
Copy `arena-context/agents/arena-builder.md` → `.claude/agents/arena-builder.md`
Copy `arena-context/commands/` → `.claude/commands/`

These load automatically via path scoping — no manual context needed.

## After Each Phase

```bash
ruff check . --fix && ruff format .
mypy --strict letsbuild/arena/
pytest tests/arena/ -v
git add -A && git commit -m "feat(arena): phase X complete"
```
