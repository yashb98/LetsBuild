# Rules: Pydantic Models (letsbuild/models/**/*)

## Model Organisation

One file per layer, plus shared:

- `shared.py` — StructuredError, GateResult, PipelineMetrics, BudgetInfo
- `intake_models.py` — JDAnalysis, Skill, TechStack, RoleCategory
- `intelligence_models.py` — CompanyProfile, ResearchResult, SubAgentResult
- `matcher_models.py` — GapAnalysis, MatchScore, GapItem
- `architect_models.py` — ProjectSpec, FeatureSpec, ADR, SandboxValidationPlan
- `forge_models.py` — TaskGraph, Task, AgentOutput, ForgeOutput, CodeModule
- `publisher_models.py` — PublishResult, CommitPlan, RepoConfig
- `content_models.py` — ContentOutput, ContentFormat
- `memory_models.py` — MemoryRecord, JudgeVerdict, DistilledPattern, ReasoningBankQuery
- `config_models.py` — AppConfig, SkillConfig, ModelConfig

## Pydantic v2 Conventions

- Use `model_validator(mode="after")` for cross-field validation
- Use `Field(description=...)` on every field — these become tool schema descriptions
- Use `Literal` for fixed enums, `Enum` for extensible categories
- Nullable fields: `field: str | None = None` — NEVER use `Optional[str]`
- Use `ConfigDict(strict=True)` on all models

## Schema ↔ Tool Schema Correspondence

Models in this directory serve dual purpose:
1. Internal validation via Pydantic
2. Claude tool_use schemas via `.model_json_schema()`

When adding a field, always consider: "Will this appear in the tool schema? Is the description clear enough for Claude to fill it correctly?"

## Extensible Enums Pattern

```python
class RoleCategory(str, Enum):
    FULL_STACK = "full_stack_engineer"
    ML_ENGINEER = "ml_engineer"
    # ... 13 more ...
    OTHER = "other"

class JDAnalysis(BaseModel):
    role_category: RoleCategory
    role_category_detail: str | None = None  # Only filled when role_category == OTHER
```

## Validation Rules

- All monetary amounts in GBP (float, 2 decimal places)
- All timestamps as `datetime` with UTC timezone
- All scores as `float` in range [0.0, 100.0]
- All IDs as `str` (UUID4 format)
- Tech stack items as lowercase strings
