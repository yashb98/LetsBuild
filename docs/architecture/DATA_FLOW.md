# LetsBuild Data Flow — v3.0

## Pipeline Data Flow

```
JD Input (text/URL)
    │
    ▼
┌──────────────────┐
│  L1: Intake       │──→ JDAnalysis
│  (tool_use forced)│     ├── role_title, role_category, seniority
└──────────────────┘     ├── required_skills[], preferred_skills[]
    │                     ├── tech_stack, domain_keywords
    ▼                     └── key_responsibilities[]
┌──────────────────┐
│  L2: Intelligence │──→ CompanyProfile
│  (6 sub-agents)   │     ├── tech_stack_signals[]
└──────────────────┘     ├── engineering_culture
    │                     ├── business_context
    ▼                     └── confidence_score (0-100)
┌──────────────────┐
│  L3: Matcher      │──→ GapAnalysis
│  (6-dim scoring)  │     ├── overall_score (0-100)
└──────────────────┘     ├── strong_matches[], demonstrable_gaps[]
    │                     ├── learnable_gaps[], hard_gaps[]
    ▼                     └── portfolio_redundancy[]
┌──────────────────┐
│  L4: Architect    │──→ ProjectSpec
│  (skill-driven)   │     ├── project_name, one_liner
└──────────────────┘     ├── file_tree, feature_specs[]
    │                     ├── sandbox_validation_plan
    ▼                     └── adr_list[]
┌──────────────────┐
│  L5: Code Forge   │──→ ForgeOutput
│  (multi-agent)    │     ├── code_modules[]
└──────────────────┘     ├── test_results
    │                     ├── review_verdict
    ▼                     └── quality_score (0-100)
┌──────────────────┐
│  L6: Publisher    │──→ PublishResult
│  (GitHub API)     │     ├── repo_url
└──────────────────┘     ├── commit_shas[]
    │                     └── readme_url
    ▼
┌──────────────────┐
│  L7: Content      │──→ ContentOutput[]
│  (multi-format)   │     ├── youtube_script
└──────────────────┘     ├── blog_post
                          ├── linkedin_carousel
                          └── twitter_thread
```

## PipelineState Accumulation

The `PipelineState` object flows through every layer, accumulating results:

```python
# After L1
state.jd_analysis = JDAnalysis(...)

# After L2
state.company_profile = CompanyProfile(...)

# After L3
state.gap_analysis = GapAnalysis(...)

# After L4
state.project_spec = ProjectSpec(...)

# After L5
state.forge_output = ForgeOutput(...)

# After L6
state.publish_result = PublishResult(...)

# After L7
state.content_outputs = [ContentOutput(...), ...]
```

## Cross-Cutting Data Flows

### Memory (L8) — reads and writes at multiple points:

```
L2 reads:  CompanyProfile cache (skip research if fresh)
L4 reads:  ReasoningBank patterns (bias toward proven designs)
L5 reads:  ReasoningBank code strategies (reduce retries)
L6 reads:  Portfolio Registry (avoid duplicating existing repos)

L2 writes: CompanyProfile (cache for future runs)
L5 writes: JUDGE verdict (quality, retries, cost, time)
L6 writes: Portfolio Registry (new repo registered)
L8 writes: DISTILL patterns (every 10 runs)
```

### Hooks (L9) — intercepts at specific events:

```
PreToolUse:          Block policy-violating tool calls
PostToolUse:         Trim verbose tool output, normalise data
PostCodeGeneration:  Run security scan (trufflehog)
PostReview:          Route FAIL verdicts to retry loop
PrePublish:          Final quality + security gate
PostPipeline:        Record JUDGE verdict, notify user
```

### Middleware — wraps every layer execution:

```
Before L(n):  RequestValidation → ThreadData → SandboxAcquisition
              → SkillLoader → MemoryRetrieval → BudgetGuard
After L(n):   QualityGate → NotificationDispatch
              → MemoryPersistence → CleanupHandler
```

## Context Flow per Agent (Code Forge)

```
Planner receives:   ProjectSpec + skill file
Coder receives:     Task assignment + module dependencies + skill file
Tester receives:    Generated code + test plan from ProjectSpec
Reviewer receives:  Generated code + ProjectSpec + quality checklist (NO coder context)
Integrator receives: All modules + integration test plan
```

## Error Flow

```
Any layer failure:
    │
    ├── StructuredError created with errorCategory + isRetryable
    ├── Appended to state.errors[]
    │
    ├── If transient + isRetryable:
    │     └── Retry (max 2 per layer) with backoff
    │
    ├── If business/permission + not retryable:
    │     └── Skip layer, continue pipeline, annotate confidence
    │
    └── If ≥3 layers failed:
          └── Abort pipeline, notify user with error summary
```
