# LetsBuild 🏗️

> **Autonomous Portfolio Factory** — JD in, published GitHub repo out.

LetsBuild is an open-source autonomous pipeline that transforms job descriptions into production-ready, company-tailored GitHub repositories with realistic commit histories, Architecture Decision Records, CI/CD, tutorials, and content.

**23 production-grade patterns.** DeerFlow infrastructure. Anthropic Certified Architect patterns. Ruflo intelligence.

## How It Works

```
Job Description → Intake → Company Research → Match & Score
    → Project Architect → Code Forge (sandboxed) → GitHub Publisher
    → Content Factory (blog, YouTube, LinkedIn)
```

## Architecture

10 orchestrated layers with cross-cutting middleware, policy gates, and a self-learning ReasoningBank.

| Layer | Name | What It Does |
|-------|------|-------------|
| 0 | Agent Harness | Middleware chain, Docker sandbox, compiled policy gates |
| 1 | Intake Engine | JD parsing with guaranteed structured output |
| 2 | Company Intelligence | 6 parallel research sub-agents |
| 3 | Match & Score | 6-dimension weighted matching + gap analysis |
| 4 | Project Architect | Skill-driven project design with ADRs |
| 5 | Code Forge | Multi-agent sandboxed code generation |
| 6 | GitHub Publisher | Realistic commits, README, CI/CD |
| 7 | Content Factory | YouTube scripts, blogs, LinkedIn carousels |
| 8 | Memory + ReasoningBank | RETRIEVE → JUDGE → DISTILL → CONSOLIDATE |
| 9 | Agent Hooks | Deterministic enforcement at every boundary |

## Quick Start

```bash
# Clone
git clone https://github.com/yashb98/LetsBuild.git
cd LetsBuild

# Install
pip install -e ".[dev]"

# Configure
cp letsbuild.yaml.example letsbuild.yaml
# Edit letsbuild.yaml with your API keys

# Run
letsbuild run --url "https://example.com/job-posting"
```

## Key Features

- **95-99% ATS Match Score** — Projects tailored to specific JD requirements
- **Sandboxed Code Generation** — Every line of code runs in Docker before publishing
- **Independent Code Review** — Reviewer agent has zero context from the Coder
- **Self-Learning** — Gets 20%+ better after 50 runs via ReasoningBank
- **15+ Project Categories** — Full-stack, ML, data engineering, agentic AI, NLP, CV, and more
- **Realistic Git History** — Conventional commits spread across days, not a single mega-commit
- **Architecture Decision Records** — Every project includes ADRs demonstrating senior-level thinking

## For Claude Code Users

This repo ships with a complete `.claude/` configuration:

- `CLAUDE.md` — Project brain with architecture map, coding patterns, build commands
- `.claude/rules/` — Path-scoped rules for agents, testing, skills, pipeline, models, security
- `.claude/commands/` — `/test-jd`, `/add-skill`, `/review-output`, `/add-layer`
- `.claude/agents/` — code-reviewer, research-agent, quality-auditor, skill-author
- `.claude/skills/` — benchmark, research-sprint, code-review
- `.claude/hooks/` — PostToolUse auto-lint, PreToolUse safety guard, Stop summary

## Documentation

- [Architecture Reference](docs/architecture/ARCHITECTURE.md)
- [Data Flow](docs/architecture/DATA_FLOW.md)
- [Skill Authoring Guide](docs/contributing/SKILL_AUTHORING.md)
- [100-Step Execution Plan](docs/EXECUTION_PLAN_100_STEPS.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Key pathways:
- **Project Skills** — New project type templates
- **Code Gen Skills** — Language/framework patterns
- **Research Plugins** — Industry-specific data sources
- **Quality Benchmarks** — JD test suites with expected scores

## Built With

- [Anthropic Claude](https://anthropic.com) — AI backbone
- [DeerFlow](https://github.com/bytedance/deer-flow) — Infrastructure patterns
- [Ruflo](https://github.com/ruvnet/ruflo) — Intelligence patterns

## License

MIT — see [LICENSE](LICENSE)

---

*23 production-grade patterns. One domain-specific missile. The future of developer portfolios starts here.*
