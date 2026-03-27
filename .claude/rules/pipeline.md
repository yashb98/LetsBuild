# Rules: Pipeline & Harness Code (letsbuild/pipeline/**/* , letsbuild/harness/**/*)

## Middleware Pattern

Every middleware implements the `Middleware` base class:

```python
class Middleware(ABC):
    @abstractmethod
    async def before(self, state: PipelineState) -> PipelineState:
        """Pre-processing. Return modified state or raise to abort."""
        ...

    @abstractmethod
    async def after(self, state: PipelineState) -> PipelineState:
        """Post-processing. Return modified state."""
        ...
```

## Middleware Chain Order (NEVER reorder without ADR)

1. RequestValidation
2. ThreadData
3. SandboxAcquisition
4. SkillLoader
5. MemoryRetrieval
6. BudgetGuard + LearnedRouter
7. QualityGate
8. NotificationDispatch
9. MemoryPersistence
10. CleanupHandler

## PipelineState

`PipelineState` is the single object passed through all layers. It accumulates results:

```python
class PipelineState(BaseModel):
    thread_id: str
    jd_analysis: JDAnalysis | None = None
    company_profile: CompanyProfile | None = None
    gap_analysis: GapAnalysis | None = None
    project_spec: ProjectSpec | None = None
    forge_output: ForgeOutput | None = None
    publish_result: PublishResult | None = None
    content_outputs: list[ContentOutput] = []
    errors: list[StructuredError] = []
    metrics: PipelineMetrics = PipelineMetrics()
    budget_remaining: float = 50.0
    current_layer: int = 0
```

## Gate Enforcement

Gates are in `letsbuild/harness/gates.py`. They are pure Python functions (no LLM calls):

- Gates return `GateResult(passed=bool, reason=str, blocking=bool)`
- Blocking gates halt the pipeline. Non-blocking gates log warnings.
- Gates are evaluated at layer boundaries by the PipelineController
- NEVER put gate logic in prompts or rely on the LLM to enforce gates

## Pipeline Controller

`letsbuild/pipeline/controller.py` orchestrates:
1. Load config from `letsbuild.yaml`
2. Build middleware chain
3. For each layer 1→7: run middleware.before() → execute layer → run middleware.after() → evaluate gates
4. Layer 8 (Memory) runs asynchronously after pipeline completes
5. Layer 9 (Hooks) fires at specific events during execution

## Error Propagation

- Layer failures append to `state.errors` with `StructuredError`
- Transient errors trigger retry (max 2 retries per layer)
- Business/permission errors skip the layer and continue
- If ≥3 layers fail, pipeline aborts and notifies user

## Configuration

- `letsbuild.yaml` is the single source of truth for runtime config
- Environment variables override YAML values: `LETSBUILD_<SECTION>_<KEY>`
- Secrets MUST be env vars, never in YAML: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `SERPAPI_KEY`
