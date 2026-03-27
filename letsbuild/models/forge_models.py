"""Pydantic v2 models for Layer 5: Code Forge."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from letsbuild.models.shared import StructuredError  # noqa: TC001


class SwarmTopology(StrEnum):
    """Topology pattern used by the Code Forge agent swarm."""

    HIERARCHICAL = "hierarchical"
    MESH = "mesh"
    SEQUENTIAL = "sequential"
    RING = "ring"


class AgentRole(StrEnum):
    """Role of an agent within the Code Forge swarm."""

    PLANNER = "planner"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    INTEGRATOR = "integrator"


class TaskStatus(StrEnum):
    """Current status of a task in the task graph."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Task(BaseModel):
    """A single unit of work assigned to an agent in the Code Forge."""

    model_config = ConfigDict(strict=True)

    task_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this task (UUID4).",
    )
    module_name: str = Field(
        description="Name of the module or component this task produces.",
    )
    description: str = Field(
        description="What this task should accomplish.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Task IDs that must complete before this task can start.",
    )
    assigned_agent: AgentRole | None = Field(
        default=None,
        description="The agent role assigned to execute this task.",
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current execution status of this task.",
    )
    estimated_complexity: int = Field(
        description="Estimated complexity on a 1-10 scale.",
    )
    retry_count: int = Field(
        default=0,
        description="Number of times this task has been retried.",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries allowed for this task.",
    )

    @field_validator("estimated_complexity")
    @classmethod
    def validate_complexity(cls, v: int) -> int:
        """Ensure complexity is within the 1-10 range."""
        if v < 1 or v > 10:
            msg = "estimated_complexity must be between 1 and 10"
            raise ValueError(msg)
        return v


class TaskGraph(BaseModel):
    """Directed acyclic graph of tasks for the Code Forge to execute."""

    model_config = ConfigDict(strict=True)

    tasks: list[Task] = Field(
        description="Ordered list of tasks forming the execution graph.",
    )
    topology: SwarmTopology = Field(
        default=SwarmTopology.HIERARCHICAL,
        description="Swarm topology pattern used for agent coordination.",
    )
    total_estimated_complexity: int = Field(
        description="Sum of estimated complexity across all tasks.",
    )


class CodeModule(BaseModel):
    """A single code module produced by a Coder agent."""

    model_config = ConfigDict(strict=True)

    module_path: str = Field(
        description="Relative file path of the module within the project.",
    )
    content: str = Field(
        description="Full source code content of the module.",
    )
    language: str = Field(
        description="Programming language of the module (e.g. 'python', 'typescript').",
    )
    loc: int = Field(
        description="Lines of code in this module.",
    )
    test_file_path: str | None = Field(
        default=None,
        description="Relative path to the corresponding test file, if any.",
    )


class ReviewVerdict(StrEnum):
    """Verdict from the independent Reviewer agent."""

    PASS = "pass"
    FAIL = "fail"
    PASS_WITH_SUGGESTIONS = "pass_with_suggestions"


class AgentOutput(BaseModel):
    """Output produced by a single agent execution within the Code Forge."""

    model_config = ConfigDict(strict=True)

    agent_role: AgentRole = Field(
        description="Role of the agent that produced this output.",
    )
    task_id: str = Field(
        description="ID of the task this output corresponds to.",
    )
    success: bool = Field(
        description="Whether the agent completed the task successfully.",
    )
    output_modules: list[CodeModule] = Field(
        default_factory=list,
        description="Code modules produced by this agent execution.",
    )
    error: StructuredError | None = Field(
        default=None,
        description="Structured error if the agent failed.",
    )
    tokens_used: int = Field(
        description="Total LLM tokens consumed by this agent execution.",
    )
    execution_time_seconds: float = Field(
        description="Wall-clock time for this agent execution in seconds.",
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries attempted for this task.",
    )


class ForgeOutput(BaseModel):
    """Complete output from a Code Forge pipeline run (Layer 5)."""

    model_config = ConfigDict(strict=True)

    code_modules: list[CodeModule] = Field(
        description="All code modules produced by the forge.",
    )
    test_results: dict[str, bool] = Field(
        description="Test results mapping test name to pass/fail.",
    )
    review_verdict: ReviewVerdict = Field(
        description="Verdict from the independent Reviewer agent.",
    )
    review_comments: list[str] = Field(
        default_factory=list,
        description="Comments and suggestions from the Reviewer agent.",
    )
    quality_score: float = Field(
        description="Overall quality score from 0.0 to 100.0.",
    )
    total_tokens_used: int = Field(
        description="Total LLM tokens consumed across all agents.",
    )
    total_retries: int = Field(
        description="Total number of retries across all tasks.",
    )
    topology_used: SwarmTopology = Field(
        description="Swarm topology that was used for this forge run.",
    )
    agent_outputs: list[AgentOutput] = Field(
        default_factory=list,
        description="Individual outputs from each agent execution.",
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the forge run completed (UTC).",
    )

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: float) -> float:
        """Ensure quality score is within the 0-100 range."""
        if v < 0.0 or v > 100.0:
            msg = "quality_score must be between 0.0 and 100.0"
            raise ValueError(msg)
        return v
