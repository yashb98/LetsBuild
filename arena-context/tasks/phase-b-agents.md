# Phase B: Arena Agents

## Goal
Create 5 tournament agents that extend the existing BaseAgent.

## Pre-read (load these before starting)
- `letsbuild/forge/base_agent.py` — BaseAgent class you're extending
- `letsbuild/forge/agents/coder.py` — CoderAgent pattern to follow for Builder
- `letsbuild/forge/agents/reviewer.py` — ReviewerAgent pattern to follow for Critic
- `letsbuild/forge/agents/planner.py` — PlannerAgent pattern to follow for Architect
- `letsbuild/forge/tools.py` — existing tool schemas
- `letsbuild/models/arena_models.py` — your Phase A models

## Files to Create

### 1. `letsbuild/arena/agents/architect.py`

Extends `BaseAgent(role=ArenaAgentRole.ARCHITECT)`. Model: opus.

**System prompt:** You are the lead architect for a competitive hackathon team. Your job: analyze the challenge brief, research approaches (web search, GitHub repos, papers), create ARCHITECTURE.md with stack decisions and component design, decompose into tasks for Builder/Frontend/Tester.

**Tools (max 5):** web_search, read_file, write_file, bash (for `find`, `git log`), spawn_subtask

**process_result:** Extract ARCHITECTURE.md content and task list from final response.

### 2. `letsbuild/arena/agents/builder.py`

Wraps the existing `letsbuild.forge.agents.coder.CoderAgent` — do NOT reimplement code generation. Add tournament context (challenge brief, ARCHITECTURE.md, time remaining) to task_context.

```python
class ArenaBuilder(BaseAgent):
    """Tournament-aware code builder. Wraps CoderAgent with challenge context."""

    def __init__(self, llm_client, model="claude-sonnet-4-6"):
        super().__init__(role=ArenaAgentRole.BUILDER, llm_client=llm_client, model=model)
        self._coder = CoderAgent(llm_client=llm_client, model=model)  # reuse
```

**Tools:** Same as CoderAgent — read_file, write_file, bash, list_files, search_code

### 3. `letsbuild/arena/agents/frontend.py`

Extends `BaseAgent(role=ArenaAgentRole.FRONTEND)`. Model: sonnet.

**System prompt:** You are a frontend/UI engineer for a competitive hackathon. Build responsive, polished user interfaces. Use modern frameworks (React/Next.js/Tailwind or whatever ARCHITECTURE.md specifies).

**Tools (max 5):** read_file, write_file, bash (npm/vite commands), list_files, web_search

### 4. `letsbuild/arena/agents/critic.py`

Extends `BaseAgent(role=ArenaAgentRole.CRITIC)`. Model: opus.

**System prompt:** You are an adversarial code reviewer. Your job is to BREAK things. Find bugs, security holes, architectural flaws, missing edge cases. You have ZERO context from the build process — you see only the code and the challenge brief. During cross-review, you review the OPPOSING team's code.

**Tools (max 5):** read_file, grep, glob, bash (pytest/ruff only — NO write access)

**Critical:** `disallowedTools` includes Write, Edit. Read-only access enforced.

### 5. `letsbuild/arena/agents/tutor.py`

Extends `BaseAgent(role=ArenaAgentRole.TUTOR)`. Model: haiku (speed > depth).

**System prompt:** You are an AI sports commentator watching a live coding competition. Read the agent activity logs and explain what's happening, what strategies teams are using, and what a spectator should pay attention to. Be engaging but technical.

**Tools (max 3):** read_file, grep, glob — read-only, reads logs and code

### 6. Tests

`tests/arena/test_agents.py`:
- Test each agent is a subclass of BaseAgent
- Test tool count ≤ 5
- Test system_prompt returns non-empty string
- Test run() with mocked LLM returns AgentOutput
- Test Critic has no write tools
- Test Builder wraps CoderAgent correctly

## Verification
```bash
ruff check letsbuild/arena/agents/ --fix && ruff format .
mypy --strict letsbuild/arena/agents/
pytest tests/arena/test_agents.py -v
```
