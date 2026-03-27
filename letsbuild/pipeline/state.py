"""PipelineState model that accumulates results from all pipeline layers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from letsbuild.models.architect_models import ProjectSpec  # noqa: TC001
from letsbuild.models.config_models import SkillConfig  # noqa: TC001
from letsbuild.models.content_models import ContentOutput  # noqa: TC001
from letsbuild.models.forge_models import ForgeOutput  # noqa: TC001
from letsbuild.models.intake_models import JDAnalysis  # noqa: TC001
from letsbuild.models.intelligence_models import CompanyProfile  # noqa: TC001
from letsbuild.models.matcher_models import GapAnalysis  # noqa: TC001
from letsbuild.models.publisher_models import PublishResult  # noqa: TC001
from letsbuild.models.shared import PipelineMetrics, StructuredError


class PipelineState(BaseModel):
    """Central state object that flows through every pipeline layer, accumulating results.

    After each layer completes, its output is written to the corresponding field:
    L1 -> jd_analysis, L2 -> company_profile, L3 -> gap_analysis, L4 -> project_spec,
    L5 -> forge_output, L6 -> publish_result, L7 -> content_outputs.

    Cross-cutting concerns (errors, metrics, budget, sandbox) are updated throughout.
    """

    model_config = ConfigDict(strict=True)

    # --- Identity & Progress ---
    thread_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this pipeline run (UUID4).",
    )
    current_layer: int = Field(
        default=0,
        ge=0,
        le=9,
        description="Current pipeline layer being executed (0-9).",
    )

    # --- Raw Input ---
    jd_text: str | None = Field(
        default=None,
        description="Raw job description text provided as input.",
    )
    jd_url: str | None = Field(
        default=None,
        description="URL of the job description, if provided.",
    )

    # --- Layer Outputs ---
    jd_analysis: JDAnalysis | None = Field(
        default=None,
        description="Structured JD analysis produced by Layer 1 (Intake Engine).",
    )
    company_profile: CompanyProfile | None = Field(
        default=None,
        description="Company intelligence profile produced by Layer 2.",
    )
    gap_analysis: GapAnalysis | None = Field(
        default=None,
        description="Match and gap analysis produced by Layer 3.",
    )
    project_spec: ProjectSpec | None = Field(
        default=None,
        description="Project specification produced by Layer 4 (Project Architect).",
    )
    forge_output: ForgeOutput | None = Field(
        default=None,
        description="Code generation output produced by Layer 5 (Code Forge).",
    )
    publish_result: PublishResult | None = Field(
        default=None,
        description="GitHub publish result produced by Layer 6.",
    )
    content_outputs: list[ContentOutput] = Field(
        default_factory=list,
        description="Content pieces produced by Layer 7 (Content Factory).",
    )

    # --- Cross-Cutting State ---
    errors: list[StructuredError] = Field(
        default_factory=list,
        description="Accumulated structured errors from all layers.",
    )
    metrics: PipelineMetrics = Field(
        default_factory=PipelineMetrics,
        description="Metrics collected during the pipeline run.",
    )
    budget_remaining: float = Field(
        default=50.0,
        description="Remaining API budget in GBP for this run.",
    )
    sandbox_id: str | None = Field(
        default=None,
        description="Docker sandbox container ID assigned to this run.",
    )
    workspace_path: str | None = Field(
        default=None,
        description="Temporary workspace directory path for this run.",
    )
    skill_configs: list[SkillConfig] = Field(
        default_factory=list,
        description="Skill configurations loaded by the SkillLoader middleware.",
    )

    # --- Timestamps ---
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this pipeline run started (UTC).",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When this pipeline run completed (UTC). Set when done.",
    )

    # --- Helper Methods ---

    def add_error(self, error: StructuredError) -> None:
        """Append a structured error to the accumulated errors list."""
        self.errors.append(error)

    def is_failed(self) -> bool:
        """Return True if 3 or more errors have accumulated, triggering pipeline abort."""
        return len(self.errors) >= 3

    def advance_layer(self) -> None:
        """Increment current_layer to move to the next pipeline stage."""
        self.current_layer += 1
