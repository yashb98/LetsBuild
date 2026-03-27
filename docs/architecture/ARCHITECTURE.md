# LetsBuild Architecture Reference — v3.0

> Comprehensive architecture specification for the 10-layer autonomous portfolio factory.
> Source of truth for all implementation decisions.

## System Overview

LetsBuild transforms job descriptions into production-ready GitHub repositories through a 10-layer pipeline. It integrates 23 production-grade patterns from three sources: DeerFlow (8 patterns), Claude Certified Architect (9 patterns), and Ruflo (6 patterns).

## Layer Map

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 9: Agent Hooks                      │
│              PostToolUse · PrePublish · PreToolUse           │
├─────────────────────────────────────────────────────────────┤
│  L1 Intake → L2 Intelligence → L3 Match → L4 Architect     │
│        → L5 Code Forge → L6 Publisher → L7 Content          │
├─────────────────────────────────────────────────────────────┤
│                Layer 8: Memory + ReasoningBank               │
│           RETRIEVE → JUDGE → DISTILL → CONSOLIDATE          │
├─────────────────────────────────────────────────────────────┤
│          Layer 0: Agent Harness + Guidance Control           │
│    Middleware Chain (10-stage) · Docker Sandbox · Gates      │
└─────────────────────────────────────────────────────────────┘
```

## Layer 0: Agent Harness & Guidance Control Plane

**Sources:** DeerFlow (middleware, sandbox, dual-config) + Ruflo (compiled policy gates)

### Middleware Chain (10-Stage)

| # | Middleware | Responsibility |
|---|-----------|----------------|
| 1 | RequestValidation | Input schema validation, reject malformed |
| 2 | ThreadData | Isolated workspace, unique thread ID |
| 3 | SandboxAcquisition | Docker sandbox from pre-warmed pool |
| 4 | SkillLoader | Progressive skill loading based on JD |
| 5 | MemoryRetrieval | Company cache, user profile, ReasoningBank |
| 6 | BudgetGuard + LearnedRouter | Q-Learning model selection, budget caps |
| 7 | QualityGate | Compiled policy validation at layer boundaries |
| 8 | NotificationDispatch | Telegram, Slack, Discord, WebSocket |
| 9 | MemoryPersistence | Async write of results and JUDGE verdicts |
| 10 | CleanupHandler | Release sandbox, archive, compute metrics |

### Docker Sandbox

- Base image: `letsbuild/sandbox:latest` (Ubuntu 24.04 + Python 3.12 + Node 20 + Go + Rust)
- Filesystem: `/mnt/workspace/`, `/mnt/skills/` (read-only), `/mnt/outputs/`
- Limits: 4 CPU, 8GB RAM, 20GB disk, 30min lifetime
- Pool: 3 pre-warmed standby containers
- Security: rootless, outbound-only networking, fresh per run

### Guidance Control Plane (4 Compiled Gates)

| Gate | Blocks If | Override |
|------|-----------|----------|
| PublishGate | sandbox_validation_plan not fully passed | None |
| SecurityGate | trufflehog/gitleaks detects secrets | None |
| QualityGate | quality score < threshold (default 70) | Per-skill config |
| BudgetGate | per-run API cost exceeds maximum | None |

Gates are deterministic Python code, not prompt instructions.

## Layer 1: Intake Engine

**Pattern:** tool_choice forced selection for guaranteed structured output.

- Input: JD text or URL (REST, CLI, web, webhook, CSV, file watch, MCP, messaging)
- Processing: 3-stage skill extraction (rule-based → spaCy NER → LLM refinement)
- Output: `JDAnalysis` Pydantic model
- tool_choice: `{"type": "tool", "name": "extract_jd_analysis"}`

## Layer 2: Company Intelligence

**Patterns:** DeerFlow sub-agent parallelism + structured error responses.

- 6 parallel sub-agents: WebPresence, TechBlog, GitHubOrg, BusinessIntel, NewsMonitor, CultureProbe
- Each sub-agent has ≤3-4 scoped tools
- All failures return `StructuredError(errorCategory, isRetryable, partialResults)`
- Memory-accelerated: <30 days cached → skip; 30-90 days → news only; >90 days → full research

## Layer 3: Match & Score Engine

- 6-dimension weighted matching: Hard Skills (30%), Tech Stack (20%), Domain (15%), Portfolio (15%), Seniority (10%), Soft Skills (10%)
- Gap categories: strong_matches, demonstrable_gaps, learnable_gaps, hard_gaps, portfolio_redundancy

## Layer 4: Project Architect

**Patterns:** Progressive skills + ADRs in every project.

- Loads skill files based on JD role_category
- Outputs: ProjectSpec with file_tree, feature_specs, sandbox_validation_plan, adr_list
- Design principles: company-relevant, skill-showcasing, seniority-calibrated, sandbox-validated

## Layer 5: Code Forge

**Patterns:** stop_reason loops + scoped tools + independent review + configurable topology.

### Agents

| Agent | Model | Tools (max 5) | Sandbox |
|-------|-------|---------------|---------|
| Planner | Opus | read_file, list_directory | Read-only |
| Coder (×N) | Sonnet | write_file, bash_execute, install_package, read_file | Full |
| Tester | Sonnet | read_file, bash_execute, write_file | Full |
| Reviewer | Opus | read_file, list_directory | Read-only |
| Integrator | Sonnet | read_file, write_file, bash_execute, docker_build | Full |

### Swarm Topologies

| Topology | When | Pattern |
|----------|------|---------|
| Hierarchical | Most projects | Planner → Coders → Tester → Reviewer → Integrator |
| Mesh | Tightly coupled | Coders share message bus |
| Sequential | Strict deps | Each waits for previous |
| Ring | Large projects (10+) | Ring-pass validated output |

## Layer 6: GitHub Publisher

- SEO-optimised naming, auto-topics, OG image
- ADR directory: `docs/decisions/`
- 7-phase commit strategy spread across 3-7 days
- Conventional Commits format

## Layer 7: Content Factory

- YouTube scripts, blog posts (2000-3000w), LinkedIn carousels, Twitter threads, project walkthroughs

## Layer 8: Memory + ReasoningBank

**Patterns:** DeerFlow memory + Ruflo ReasoningBank learning pipeline.

### Learning Pipeline

1. **RETRIEVE:** HNSW query for similar past generations before Project Architect runs
2. **JUDGE:** Structured verdict after every Code Forge run (pass/fail, score, retries, cost)
3. **DISTILL:** Every 10 runs, extract learnable patterns from JUDGE verdicts
4. **CONSOLIDATE:** EWC++ prevents catastrophic forgetting across domains

### Memory Types

| Type | Storage | TTL | Purpose |
|------|---------|-----|---------|
| Company Profiles | SQLite + embeddings | 90 days | Cached research |
| User Profile | SQLite | Permanent | Skills, repos |
| Portfolio Registry | SQLite + GitHub API | Permanent | Generated projects |
| ReasoningBank | SQLite + HNSW | Permanent (EWC) | Learned strategies |
| JUDGE Verdicts | SQLite | 6 months | Raw success/failure |
| Skill Taxonomy | JSON + embeddings | Monthly | 2,500+ skills |
| Pipeline Metrics | SQLite | Permanent | Timing, cost, quality |

## Layer 9: Agent Hooks

| Hook | When | Purpose |
|------|------|---------|
| PreToolUse | Before tool call | Block policy violations, enforce scoping |
| PostToolUse | After tool result | Trim verbose output, normalise data |
| PrePublish | Before GitHub create | Final quality gate |
| PostCodeGeneration | After Coder batch | Security scan |
| PostReview | After Reviewer verdict | Auto-route to retry if FAIL |
| PostPipeline | After completion | JUDGE verdict, user notification |

## Multi-Model Strategy

| Task | Default | tool_choice | Fallback | Cost |
|------|---------|-------------|----------|------|
| Architecture | Opus | forced: design_project | GPT-4o | £2-5 |
| Code Gen | Sonnet | auto | Qwen3-8B | £5-15 |
| Testing | Sonnet | auto | Qwen3-8B | £2-5 |
| Review | Opus | auto | Sonnet | £2-4 |
| Skill Extract | Haiku | forced: extract_jd | GPT-4o-mini | £0.10-0.50 |
| Research | Sonnet | auto | DeepSeek v3 | £1-3 |
| Content | Sonnet | auto | Qwen3-8B | £2-5 |

Q-Learning router evolves from static rules after 20+ runs.

## Context Engineering

1. PostToolUse trimming of verbose tool output
2. Structured "case facts" block at context start
3. Position-aware ordering (key findings first)
4. Sub-agent context isolation
