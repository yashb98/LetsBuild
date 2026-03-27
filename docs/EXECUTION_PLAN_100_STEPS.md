# LetsBuild v3.0 — Complete Execution Plan (100 Steps)

> From zero to public launch. Every step builds on the previous.
> Estimated total: 8 weeks. Each step is a discrete, testable unit of work.

---

## PHASE 1: FOUNDATION (Steps 1-25) — Weeks 1-2

### Week 1: Monorepo, Models, Harness

**Step 1 — Monorepo Initialisation**
Create the full directory structure, `pyproject.toml` with `[project]`, `[project.optional-dependencies.dev]`, `Makefile`, `.gitignore`, `.editorconfig`, `LICENSE` (MIT). Init git repo. First commit.

**Step 2 — pyproject.toml Configuration**
Define all dependencies: `anthropic`, `httpx`, `pydantic>=2.0`, `typer`, `structlog`, `hnswlib`, `docker`, `pyyaml`, `jinja2`. Dev deps: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `pre-commit`. Define scripts: `letsbuild = "letsbuild.cli:app"`.

**Step 3 — .claude/ Directory Setup**
Copy all `.claude/` files (CLAUDE.md, rules/, commands/, agents/, skills/, hooks/, settings.json, .mcp.json) into the repo. Make hook scripts executable. First PR.

**Step 4 — Pydantic Shared Models**
Create `letsbuild/models/shared.py`: `StructuredError`, `GateResult`, `PipelineMetrics`, `BudgetInfo`, `ModelConfig`. All with `ConfigDict(strict=True)`, full `Field(description=...)` annotations.

**Step 5 — Intake Models**
Create `letsbuild/models/intake_models.py`: `Skill`, `TechStack`, `RoleCategory` (enum with 15+other), `JDAnalysis`. Generate JSON schema via `.model_json_schema()` and verify it works as a Claude tool schema.

**Step 6 — Intelligence Models**
Create `letsbuild/models/intelligence_models.py`: `CompanyProfile`, `ResearchResult`, `SubAgentResult`, `DataSource`. Include `confidence_score` and `data_sources` list.

**Step 7 — Matcher Models**
Create `letsbuild/models/matcher_models.py`: `GapAnalysis`, `MatchScore`, `GapItem` (with category enum: strong_match, demonstrable_gap, learnable_gap, hard_gap, portfolio_redundancy).

**Step 8 — Architect Models**
Create `letsbuild/models/architect_models.py`: `ProjectSpec`, `FeatureSpec`, `ADR`, `SandboxValidationPlan`, `FileTreeNode`. Include `skill_coverage_map` and `complexity_score`.

**Step 9 — Forge Models**
Create `letsbuild/models/forge_models.py`: `TaskGraph`, `Task`, `AgentOutput`, `ForgeOutput`, `CodeModule`, `ReviewVerdict`. Include topology enum.

**Step 10 — Publisher + Content + Memory + Config Models**
Create remaining model files: `publisher_models.py` (PublishResult, CommitPlan, RepoConfig), `content_models.py` (ContentOutput, ContentFormat), `memory_models.py` (MemoryRecord, JudgeVerdict, DistilledPattern, ReasoningBankQuery), `config_models.py` (AppConfig, SkillConfig).

**Step 11 — Model Tests**
Create `tests/models/test_all_models.py`: Test every model instantiation, serialisation, validation errors on bad input, JSON schema generation. This is your validation backbone — if models break, everything breaks.

**Step 12 — Config System**
Create `letsbuild/harness/config.py`: Load `letsbuild.yaml` into `AppConfig`. Support env var overrides (`LETSBUILD_<SECTION>_<KEY>`). Create `letsbuild.yaml.example` with all options documented.

**Step 13 — Middleware Base Class**
Create `letsbuild/harness/middleware.py`: Abstract `Middleware` class with `async before(state) -> state` and `async after(state) -> state`. Create `MiddlewareChain` that executes in order.

**Step 14 — PipelineState**
Create `letsbuild/pipeline/state.py`: `PipelineState` model that accumulates results from all layers. Include `thread_id`, `current_layer`, `errors[]`, `metrics`, `budget_remaining`.

**Step 15 — RequestValidation Middleware**
Create `letsbuild/harness/middlewares/request_validation.py`: Validates input has either JD text or URL. Rejects empty/malformed requests. Tests in `tests/harness/test_request_validation.py`.

**Step 16 — ThreadData Middleware**
Create `letsbuild/harness/middlewares/thread_data.py`: Creates isolated workspace directory under `/tmp/letsbuild/<uuid>/`, assigns thread_id. Cleanup in `after()`.

**Step 17 — Guidance Gates**
Create `letsbuild/harness/gates.py`: `PublishGate`, `SecurityGate`, `QualityGate`, `BudgetGate`. Each is a pure function returning `GateResult(passed, reason, blocking)`. Tests for both pass AND fail for each gate.

**Step 18 — CLI Skeleton**
Create `letsbuild/cli.py`: Typer app with subcommands: `ingest`, `research`, `match`, `architect`, `forge`, `publish`, `run` (full pipeline), `status`, `memory`. Each prints "Not yet implemented" for now except `ingest`.

**Step 19 — Docker Sandbox Manager**
Create `letsbuild/harness/sandbox.py`: `SandboxManager` with `async provision() -> Sandbox`, `async execute(sandbox, command) -> ExecResult`, `async cleanup(sandbox)`. Uses Docker SDK. Resource limits configured from AppConfig.

**Step 20 — Sandbox Dockerfile**
Create `sandbox/Dockerfile`: Ubuntu 24.04 base, install Python 3.12, Node 20, Go, Rust, common packages. Non-root user. Workspace at `/mnt/workspace/`.

**Step 21 — SandboxAcquisition Middleware**
Create `letsbuild/harness/middlewares/sandbox_acquisition.py`: Provisions sandbox from pool in `before()`, releases in `after()` (via CleanupHandler). Pool of 3 pre-warmed containers.

**Step 22 — structlog Configuration**
Create `letsbuild/logging.py`: Configure structlog with JSON output, context binding (thread_id, layer, agent), console renderer for dev. Every module uses `structlog.get_logger()`.

**Step 23 — Pre-commit Hooks**
Create `.pre-commit-config.yaml`: ruff check, ruff format, mypy, pytest (fast subset). Ensure CI runs the same checks.

**Step 24 — GitHub Actions CI**
Create `.github/workflows/ci.yml`: On push/PR — install deps, ruff check, mypy, pytest with coverage, upload coverage artifact. Matrix: Python 3.11 + 3.12.

**Step 25 — Makefile**
Create `Makefile` with targets: `install`, `test`, `lint`, `typecheck`, `format`, `ci` (runs all), `sandbox-build`, `clean`. Document in README.

---

## PHASE 2: INTAKE + INTELLIGENCE + MATCHING (Steps 26-45) — Week 2-3

**Step 26 — Anthropic Client Wrapper**
Create `letsbuild/harness/llm_client.py`: Async wrapper around Anthropic SDK. Supports tool_use, tool_choice config, automatic retry on transient errors, token counting, cost tracking. All LLM calls go through this.

**Step 27 — Intake Engine Core**
Create `letsbuild/intake/engine.py`: `async parse_jd(text: str) -> JDAnalysis`. Uses `tool_choice: {"type": "tool", "name": "extract_jd_analysis"}` with JDAnalysis JSON schema as tool.

**Step 28 — Intake URL Fetcher**
Create `letsbuild/intake/fetcher.py`: Fetch JD from URL. Handle HTML pages (extract job content), PDFs, plain text. Sanitise HTML (strip scripts, entities).

**Step 29 — Rule-Based Skill Extraction**
Create `letsbuild/intake/skill_extractor.py`: Pattern matching against skill taxonomy (JSON file with 2,500+ entries). Returns `list[Skill]` with confidence scores.

**Step 30 — Skill Taxonomy**
Create `skills/taxonomy.json`: Hierarchical skill taxonomy. Categories → subcategories → skills → aliases. E.g., `"python" → ["python3", "py", "cpython"]`.

**Step 31 — Intake Tests**
Create `tests/intake/test_engine.py`: Test JD parsing against 5 real JDs (stored in `tests/fixtures/sample_jds/`). Verify all fields populated, skills extracted correctly, role_category assigned.

**Step 32 — Sample JD Fixtures**
Create `tests/fixtures/sample_jds/`: 5 real JDs covering: senior fullstack fintech, junior data science, mid ML engineer, senior platform eng, staff agentic AI.

**Step 33 — Company Intelligence Coordinator**
Create `letsbuild/intelligence/coordinator.py`: Spawns 6 sub-agents in parallel via `asyncio.gather()`. Merges results into `CompanyProfile`. Handles partial failures gracefully.

**Step 34 — WebPresence Sub-Agent**
Create `letsbuild/intelligence/agents/web_presence.py`: Scrapes company website, about page, products. Scoped tools: `web_scrape`, `llm_summarise`. Returns `SubAgentResult`.

**Step 35 — GitHubOrg Sub-Agent**
Create `letsbuild/intelligence/agents/github_org.py`: Queries GitHub API for company repos, languages, stars. Scoped tools: `github_api_query`. Returns `SubAgentResult`.

**Step 36 — BusinessIntel Sub-Agent**
Create `letsbuild/intelligence/agents/business_intel.py`: Queries public business data (Companies House API, web scraping). Returns funding, size, industry.

**Step 37 — NewsMonitor Sub-Agent**
Create `letsbuild/intelligence/agents/news_monitor.py`: SerpAPI or web search for recent company news. Returns last 6 months of relevant articles.

**Step 38 — TechBlog + CultureProbe Sub-Agents**
Create remaining sub-agents. TechBlog: RSS + blog scraping. CultureProbe: Glassdoor/LinkedIn signals.

**Step 39 — Structured Error Implementation**
Implement `StructuredError` returns across all sub-agents. Test: timeout → transient+retryable; paywall → business+not_retryable; rate limit → permission+retryable.

**Step 40 — Memory Cache Check**
Create `letsbuild/intelligence/cache.py`: Check Memory (L8) for existing CompanyProfile. Implement <30d/30-90d/>90d logic.

**Step 41 — Intelligence Tests**
Create `tests/intelligence/`: Test coordinator with mocked sub-agents (all succeed, some fail, all fail). Test structured error propagation. Test cache hit/miss.

**Step 42 — Match & Score Engine**
Create `letsbuild/matcher/engine.py`: 6-dimension weighted scoring. Input: JDAnalysis + CompanyProfile + UserProfile. Output: GapAnalysis.

**Step 43 — Gap Categorisation**
Create `letsbuild/matcher/gap_analysis.py`: Categorise each skill into strong_match, demonstrable_gap, learnable_gap, hard_gap, portfolio_redundancy. Portfolio check queries Memory.

**Step 44 — ATS Score Prediction**
Create `letsbuild/matcher/ats_predictor.py`: Predict ATS match score (0-100) based on keyword overlap, tech stack alignment, experience match. Heuristic + LLM refinement.

**Step 45 — Matcher Tests + End-to-End L1-L3**
Test Match Engine with fixture data. Then: first end-to-end run: JD → JDAnalysis → CompanyProfile → GapAnalysis. Verify data flows correctly through PipelineState.

---

## PHASE 3: PROJECT ARCHITECT (Steps 46-55) — Week 3

**Step 46 — SkillLoader Middleware**
Create `letsbuild/harness/middlewares/skill_loader.py`: Reads JDAnalysis.role_category, loads matching skill files from `skills/`. Parses YAML frontmatter. Injects into PipelineState.

**Step 47 — Skill File Parser**
Create `letsbuild/architect/skill_parser.py`: Parse `.skill.md` files. Extract frontmatter (YAML), body sections. Validate required sections present. Return `SkillConfig`.

**Step 48 — Project Architect Core**
Create `letsbuild/architect/engine.py`: Input: JDAnalysis + CompanyProfile + GapAnalysis + SkillConfig. Output: ProjectSpec. Uses Claude Opus with company context, gap analysis, and skill templates.

**Step 49 — First 5 Skill Files**
Create: `skills/fullstack.skill.md`, `skills/ml-pipeline.skill.md`, `skills/data-eng.skill.md`, `skills/agentic-ai.skill.md`, `skills/data-science.skill.md`. Full frontmatter + all 8 sections.

**Step 50 — ADR Generator**
Create `letsbuild/architect/adr_generator.py`: Generate ADRs for each major design choice in ProjectSpec. Use skill file ADR templates as starting points.

**Step 51 — Sandbox Validation Plan Generator**
Create `letsbuild/architect/validation_planner.py`: Generate concrete bash commands that must pass in sandbox. Based on tech stack and skill file validation plans.

**Step 52 — ReasoningBank RETRIEVE Integration**
Create `letsbuild/architect/memory_advisor.py`: Before designing, query ReasoningBank for similar past generations. Bias ProjectSpec toward proven designs.

**Step 53 — Architect Tests**
Test ProjectSpec generation with mocked LLM. Verify: file tree coherence, feature coverage, sandbox plan has ≥3 commands, ADRs present, skill_coverage_map complete.

**Step 54 — End-to-End L1-L4**
Full run: JD → JDAnalysis → CompanyProfile → GapAnalysis → ProjectSpec. Store ProjectSpec to file. Inspect quality manually.

**Step 55 — Milestone Checkpoint**
Run `/test-jd` command against all 5 sample JDs. Verify all produce valid ProjectSpecs. Fix any issues. Commit and tag `v0.1.0-alpha`.

---

## PHASE 4: CODE FORGE (Steps 56-72) — Weeks 4-5

**Step 56 — BaseAgent Class**
Create `letsbuild/forge/base_agent.py`: Abstract base with stop_reason loop, tool execution, error handling, token tracking. All forge agents inherit from this.

**Step 57 — Tool Registry**
Create `letsbuild/forge/tools.py`: Define all sandbox tools: `write_file`, `read_file`, `bash_execute`, `install_package`, `list_directory`, `docker_build`. Each returns structured output.

**Step 58 — Tool Scoping Enforcer**
Create `letsbuild/forge/tool_scoping.py`: Validates that each agent only calls tools in its `allowed_tools` list. PreToolUse hook integration.

**Step 59 — Planner Agent**
Create `letsbuild/forge/agents/planner.py`: Decomposes ProjectSpec into TaskGraph. Each Task has: module_name, description, dependencies, estimated_complexity. Read-only sandbox access.

**Step 60 — Coder Agent**
Create `letsbuild/forge/agents/coder.py`: Implements individual tasks. Full sandbox access. Uses stop_reason loop. Tools: write_file, bash_execute, install_package, read_file.

**Step 61 — Parallel Coder Execution**
Create `letsbuild/forge/executor.py`: Run multiple Coder agents in parallel (respecting TaskGraph dependencies). `asyncio.gather()` for independent modules, sequential for dependent ones.

**Step 62 — Tester Agent**
Create `letsbuild/forge/agents/tester.py`: Writes and runs tests for generated code. Captures test output. If failures: creates structured retry context.

**Step 63 — Retry-With-Feedback Loop**
Create `letsbuild/forge/retry.py`: Implements the validation-retry pattern. Captures exact error → feeds to Coder → targeted fix → re-test. Max 3 retries per task.

**Step 64 — Reviewer Agent (Independent Instance)**
Create `letsbuild/forge/agents/reviewer.py`: Fresh Anthropic client call. Receives ONLY: code + ProjectSpec + checklist. Returns ReviewVerdict with score, blocking issues, suggestions.

**Step 65 — Integrator Agent**
Create `letsbuild/forge/agents/integrator.py`: Assembles all modules. Runs integration tests. Docker build verification. Final sandbox validation.

**Step 66 — Topology Selector**
Create `letsbuild/forge/topology.py`: Select swarm topology based on ProjectSpec module dependencies. Hierarchical (default), mesh, sequential, ring.

**Step 67 — PostCodeGeneration Hook**
Create `letsbuild/hooks/post_code_gen.py`: After Coder batch completes, run trufflehog security scan. Tag code with generation metadata.

**Step 68 — PostReview Hook**
Create `letsbuild/hooks/post_review.py`: If ReviewVerdict is FAIL, automatically route to retry-with-feedback. If PASS, proceed to Integrator.

**Step 69 — Context Compression**
Create `letsbuild/forge/context.py`: PostToolUse trimming of verbose tool output. Case facts extraction for each agent. Position-aware ordering.

**Step 70 — Forge Tests**
Test: stop_reason loop completion, tool scoping enforcement, retry-with-feedback (mock 2 failures then success), independent review isolation, topology selection.

**Step 71 — End-to-End L1-L5**
Full run: JD → ... → ForgeOutput. Inspect generated code in sandbox. Run sandbox validation commands. Fix issues.

**Step 72 — Forge Milestone**
Generate complete code for at least 2 different JD types (fullstack + data science). Both must pass sandbox validation. Tag `v0.2.0-alpha`.

---

## PHASE 5: PUBLISHER + CONTENT (Steps 73-82) — Week 5-6

**Step 73 — GitHub Client**
Create `letsbuild/publisher/github_client.py`: Async GitHub API wrapper. Create repo, create/update files, create commits, manage branches. Uses `httpx`.

**Step 74 — Commit Strategy Engine**
Create `letsbuild/publisher/commit_strategy.py`: Generate realistic commit plan: scaffolding → core modules → tests → ADRs → docs → CI/CD → polish. Timestamps spread 3-7 days. Conventional Commits.

**Step 75 — README Generator**
Create `letsbuild/publisher/readme_generator.py`: Jinja2 template. Banner → badges → architecture diagram (Mermaid) → features → quick start → ADR summary → tech stack → structure → API docs → testing → contributing → license.

**Step 76 — PrePublish Hook**
Create `letsbuild/hooks/pre_publish.py`: Final gate: all sandbox validations passed, security scan clean, README renders, quality score ≥ threshold.

**Step 77 — Publisher Integration**
Create `letsbuild/publisher/engine.py`: Orchestrates: create repo → execute commit strategy → publish files → set topics → generate OG image placeholder.

**Step 78 — Publisher Tests**
Test with mocked GitHub API. Verify: correct commit count, conventional messages, timestamps spread, README structure, ADR directory created.

**Step 79 — End-to-End L1-L6**
Full run: JD → published GitHub repo. Inspect live repo. Verify README, commit history, CI/CD workflow, ADRs.

**Step 80 — Content Factory Core**
Create `letsbuild/content/engine.py`: Orchestrates content generation. Input: ProjectSpec + ForgeOutput + PublishResult. Output: ContentOutput[] for each format.

**Step 81 — Content Templates**
Create `letsbuild/content/templates/`: Jinja2 templates for YouTube script, blog post (2000-3000w), LinkedIn carousel, Twitter thread, project walkthrough.

**Step 82 — Content Tests + E2E L1-L7**
Test content generation. Full pipeline: JD → repo + content. Tag `v0.3.0-alpha`.

---

## PHASE 6: MEMORY + LEARNING (Steps 83-90) — Week 6-7

**Step 83 — SQLite Storage Layer**
Create `letsbuild/memory/storage.py`: SQLite wrapper for all memory types. Tables: company_profiles, user_profiles, portfolio_registry, judge_verdicts, distilled_patterns, pipeline_metrics.

**Step 84 — HNSW Index**
Create `letsbuild/memory/hnsw_index.py`: hnswlib wrapper for ReasoningBank vector similarity. Embed patterns using a lightweight model. Support add, query, update.

**Step 85 — MemoryRetrieval Middleware**
Create `letsbuild/harness/middlewares/memory_retrieval.py`: Query Memory for company cache, user profile, portfolio registry, ReasoningBank patterns. Inject into PipelineState.

**Step 86 — MemoryPersistence Middleware**
Create `letsbuild/harness/middlewares/memory_persistence.py`: Async write of CompanyProfile, PortfolioEntry, JudgeVerdict, PipelineMetrics.

**Step 87 — JUDGE Implementation**
Create `letsbuild/memory/judge.py`: After every Code Forge run, record structured verdict: sandbox pass/fail, quality score, retry count per module, API cost, generation time.

**Step 88 — DISTILL Implementation**
Create `letsbuild/memory/distill.py`: Every 10 runs, analyse JUDGE verdicts. Extract patterns: "FastAPI + SQLAlchemy projects succeed 90% when schema generated first." Store as DistilledPattern.

**Step 89 — CONSOLIDATE (EWC++)**
Create `letsbuild/memory/consolidate.py`: Elastic Weight Consolidation to prevent catastrophic forgetting. When new patterns are distilled, protect existing high-value patterns.

**Step 90 — Memory Tests**
Test: CRUD operations, HNSW retrieval accuracy, JUDGE recording, DISTILL pattern extraction, cache TTL logic.

---

## PHASE 7: ECOSYSTEM (Steps 91-95) — Week 7

**Step 91 — BudgetGuard + LearnedRouter Middleware**
Create `letsbuild/harness/middlewares/budget_guard.py`: Q-Learning model router. Starts with static model mapping. After 20+ runs, learns optimal model per task category. Budget enforcement.

**Step 92 — MCP Server**
Create `letsbuild/gateway/mcp_server.py`: FastAPI-based MCP server. Tools: letsbuild_ingest, letsbuild_status, letsbuild_preview, letsbuild_approve, letsbuild_memory, letsbuild_metrics.

**Step 93 — Telegram Bot**
Create `letsbuild/gateway/telegram_bot.py`: Send JD URL → receive match score → approve ProjectSpec → receive repo link. Bidirectional progress updates.

**Step 94 — NotificationDispatch Middleware**
Create `letsbuild/harness/middlewares/notification.py`: Send progress updates to configured channels (Telegram, Slack, Discord, WebSocket). Non-blocking.

**Step 95 — Remaining 10 Skill Files**
Create: `cv.skill.md`, `nlp.skill.md`, `platform.skill.md`, `realtime.skill.md`, `api-backend.skill.md`, `autonomous.skill.md`, `mobile.skill.md`, `blockchain.skill.md`, `embedded-iot.skill.md`, `llm-finetune.skill.md`. Full specifications.

---

## PHASE 8: LAUNCH PREP (Steps 96-100) — Week 8

**Step 96 — Next.js Dashboard**
Create `web/`: Next.js 15 dashboard. Pages: submit JD, pipeline status (WebSocket live), results viewer, memory browser, metrics dashboard. Tailwind CSS.

**Step 97 — MkDocs Documentation Site**
Create `docs/`: MkDocs with Material theme. Sections: Getting Started, Architecture, Skill Authoring, API Reference, Contributing, FAQ. Deploy to GitHub Pages.

**Step 98 — Benchmark Suite**
Create `tests/fixtures/benchmark_jds/` with 10 diverse JDs. Run full benchmark. Record baseline scores. Fix any regressions.

**Step 99 — Security Audit + Performance Benchmarking**
Run trufflehog on entire codebase. Run pip-audit. Load test with 5 concurrent JDs. Profile and optimise bottlenecks. Verify all gates work under load.

**Step 100 — Launch**
- Tag `v1.0.0`
- README with demo GIF, architecture diagram, badges
- Hacker News "Show HN" post
- Reddit r/MachineLearning, r/Python, r/ClaudeAI
- LinkedIn article: "I built an AI that creates tailored portfolio projects from job descriptions"
- Twitter thread (10-15 tweets)
- Complete `.claude/` directory as showcase of Claude Code best practices
- Respond to every issue/PR/comment in first week

---

## Post-Launch Roadmap

| Week | Focus |
|------|-------|
| 9-10 | Community skill contributions, bug fixes, quick patches |
| 11-12 | Learned routing optimisation (enough data after 50+ runs), CONSOLIDATE tuning |
| 13-16 | LetsBuild Cloud (hosted version), enterprise batch processing |
| 17-20 | Plugin marketplace, community skill registry, advanced topologies |

---

## How to Use This Plan with Claude Code

1. Open Claude Code in the LetsBuild repo
2. Say: "We're on Step N. Read the execution plan and implement it."
3. Claude Code reads CLAUDE.md + relevant rules + the step description
4. Implement, test, lint, commit
5. Move to Step N+1

Each step is designed to be completable in 1-3 Claude Code sessions. Steps are ordered so you always have a working, testable system — never a half-built pile.
