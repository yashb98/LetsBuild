# Phase H: Config + Docs

## Goal
Update project config files, Claude Code configuration, and documentation.

## Files to Create/Modify

### 1. Copy arena rule (already created in Phase A)
Ensure `.claude/rules/arena.md` exists with the arena-specific rules.

### 2. Create `.claude/agents/arena-builder.md`

```yaml
---
description: "Builds and maintains the AgentForge Arena module. Understands tournament controllers, scoring, spectator systems, and challenge design."
tools: Read, Write, Bash, Grep, Glob, Agent
model: opus
maxTurns: 50
---
```

Body: brief description of arena architecture, build order reference, key files.

### 3. Create `.claude/commands/arena-duel.md`

```markdown
# /arena-duel — Quick Duel Launcher

Run a competitive duel from within Claude Code.

## Usage
/arena-duel <challenge_id>

## Steps
1. Load challenge from skills/challenges/
2. Configure two 5-agent teams (default: both Sonnet)
3. Run TournamentController
4. Print results
```

### 4. Update `pyproject.toml`

Add to optional deps:
```toml
arena = [
    "litellm>=1.40.0",
    "langfuse>=2.0.0",
    "scipy>=1.12.0",
    "redis>=5.0.0",
]
```

### 5. Update `docker-compose.yml`

Add Langfuse service under `arena` profile (see Phase D context for template).

### 6. Update `CLAUDE.md`

Add to architecture table:
```
| Arena | AgentForge Arena | `letsbuild/arena/` |
```

Add to tech stack section:
```
* **Arena:** LiteLLM (multi-provider), Langfuse (observability), scipy (ELO), Redis (streaming)
```

Add to build commands:
```bash
# Run arena duel
python -m letsbuild arena duel url-shortener

# Run arena tests
pytest tests/arena/ -v
```

### 7. Update `README.md`

Add an "AgentForge Arena" section after "Key Features":

```markdown
## AgentForge Arena 🏟️

Competitive tournament platform where AI agent teams compete to build the best applications.

- **Duel Mode** — Two teams, one challenge, head-to-head
- **5 Agents Per Team** — Architect, Builder, Frontend, Tester, Critic
- **ELO Leaderboard** — Bradley-Terry ratings track which configs win
- **Spectator Mode** — Watch agents compete in real-time via WebSocket
- **Challenge Library** — Growing collection of hackathon challenges

\`\`\`bash
# Run a duel
letsbuild arena duel url-shortener --team-a-model claude-opus-4-6 --team-b-model claude-sonnet-4-6
\`\`\`
```

### 8. Update `.claude/settings.json`

Add arena-specific permissions:
```json
"Bash(python -m letsbuild arena*)"
```

### 9. Final Verification

```bash
# Full test suite
pytest tests/ -v --cov=letsbuild --cov-report=term-missing

# Type check everything
mypy --strict letsbuild/arena/

# Lint everything
ruff check . --fix && ruff format .

# Verify CLI
python -m letsbuild arena --help
python -m letsbuild arena challenges
python -m letsbuild arena duel --help
```
