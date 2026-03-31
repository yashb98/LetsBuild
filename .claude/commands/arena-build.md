# /arena-build — Build AgentForge Arena Phase by Phase

Build a specific phase of the AgentForge Arena integration.

## Usage
```
/arena-build <phase>
```

Where `<phase>` is: a, b, c, d, e, f, g, or h

## Steps

1. Read the phase context file: `arena-context/tasks/phase-<phase>-*.md`
2. Read any pre-read files listed in the context
3. Create all files specified in the context
4. Run verification commands at the end of the context
5. Report what was built and what tests pass

## Phase Summary

- **a** — Models + Foundation (arena_models.py, worktree.py)
- **b** — Agents (architect, builder, frontend, critic, tutor)
- **c** — Scoring (JudgePanel, ELOCalculator)
- **d** — Spectator (Redis pub/sub, WebSocket)
- **e** — Challenges (engine + 5 challenge files)
- **f** — Controller (TournamentController — the main orchestrator)
- **g** — CLI + Gateway (Typer commands, WebSocket endpoint)
- **h** — Config + Docs (CLAUDE.md, README, pyproject.toml, docker-compose)
