# Phase E: Challenge Library

## Goal
Build challenge engine and create first 5 challenge files.

## Pre-read
- `skills/agentic-ai.skill.md` — YAML frontmatter + markdown format to follow
- `letsbuild/architect/skill_parser.py` — existing skill parsing logic to mirror

## Files to Create

### 1. `letsbuild/arena/challenges.py`

```python
class ChallengeEngine:
    """Loads, validates, and manages the challenge library."""

    def __init__(self, challenges_dir: str = "skills/challenges") -> None: ...

    def load(self, challenge_id: str) -> Challenge:
        """Load a .challenge.md file, parse YAML frontmatter into Challenge model."""

    def list_all(self, category: str | None = None, difficulty: int | None = None) -> list[Challenge]:
        """List available challenges, optionally filtered."""

    def generate_brief(self, challenge: Challenge) -> str:
        """Render the challenge as a markdown brief for teams to receive."""

    def get_hidden_tests(self, challenge: Challenge) -> str | None:
        """Return hidden test file content if exists, else None."""
```

Parse YAML frontmatter with `pyyaml`. Validate against Challenge model. Log with structlog.

### 2. Challenge Files: `skills/challenges/`

Create 5 `.challenge.md` files. Each has YAML frontmatter matching the Challenge model schema, then markdown body with problem description, requirements, bonus features.

**`skills/challenges/url-shortener.challenge.md`** — Difficulty 5. Build a URL shortener service with click analytics, custom aliases, expiration. Stack: any. pytest hidden tests check: redirect works, analytics counted, expired links return 410.

**`skills/challenges/task-manager.challenge.md`** — Difficulty 6. Build a task management API with projects, tasks, labels, due dates, priority sorting. Stack: Python+FastAPI or Node+Express. Hidden tests: CRUD operations, filtering, sorting, edge cases.

**`skills/challenges/cli-file-organizer.challenge.md`** — Difficulty 4. Build a CLI tool that organizes files by type, date, or size with undo support. Stack: Python+Typer. Hidden tests: file sorting, undo, dry-run mode, edge cases.

**`skills/challenges/weather-dashboard.challenge.md`** — Difficulty 5. Build a weather dashboard that aggregates multiple API sources, shows forecasts, historical comparison. Stack: any. Hidden tests: API aggregation, error handling, caching.

**`skills/challenges/code-review-bot.challenge.md`** — Difficulty 8. Build an AI-powered code review agent that reads PRs, finds bugs, suggests fixes with explanations. Stack: Python+Claude API. Hidden tests: identifies known bugs in sample code, structured output, no false positives.

Frontmatter template for each:
```yaml
---
name: <kebab-case>
display_name: "<Human Name>"
category: challenge
difficulty: <1-10>
time_limits:
  research: 1800
  architecture: 900
  build: 5400
  cross_review: 900
  fix_sprint: 900
judging_weights:
  functionality: 0.30
  code_quality: 0.20
  test_coverage: 0.15
  ux_design: 0.15
  architecture: 0.10
  innovation: 0.10
constraints:
  stack: "any"
  auth: false
  must_run: "docker-compose up or python main.py"
hidden_test_path: "tests/arena/hidden/<name>_tests.py"
---
```

### 3. Hidden Test Stubs: `tests/arena/hidden/`

Create basic pytest files for each challenge. These run inside the team sandbox during judging. ~20-30 test cases per challenge testing core requirements.

### 4. Tests

`tests/arena/test_challenges.py`:
- Test load() parses YAML frontmatter correctly
- Test list_all() returns all challenges
- Test list_all(category=...) filters correctly
- Test generate_brief() returns non-empty markdown
- Test load() with invalid file raises structured error

## Verification
```bash
ruff check letsbuild/arena/challenges.py --fix && ruff format .
pytest tests/arena/test_challenges.py -v
```
