"""Comprehensive tests for forge, publisher, content, memory, and config models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from letsbuild.models.config_models import (
    AppConfig,
    ModelTaskMapping,
    NotificationConfig,
    SandboxConfig,
    SkillConfig,
)
from letsbuild.models.content_models import ContentFormat, ContentOutput
from letsbuild.models.forge_models import (
    AgentOutput,
    AgentRole,
    CodeModule,
    ForgeOutput,
    ReviewVerdict,
    SwarmTopology,
    Task,
    TaskGraph,
    TaskStatus,
)
from letsbuild.models.memory_models import (
    DistilledPattern,
    JudgeVerdict,
    MemoryRecord,
    ReasoningBankQuery,
    VerdictOutcome,
)
from letsbuild.models.publisher_models import (
    CommitEntry,
    CommitPhase,
    CommitPlan,
    PublishResult,
    RepoConfig,
)
from letsbuild.models.shared import ErrorCategory, StructuredError

# ── forge_models: SwarmTopology ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [
        (SwarmTopology.HIERARCHICAL, "hierarchical"),
        (SwarmTopology.MESH, "mesh"),
        (SwarmTopology.SEQUENTIAL, "sequential"),
        (SwarmTopology.RING, "ring"),
    ],
)
def test_swarm_topology_values(member: SwarmTopology, value: str) -> None:
    """Each SwarmTopology member maps to the expected string."""
    assert member.value == value


def test_swarm_topology_has_exactly_four_members() -> None:
    """SwarmTopology must have exactly 4 members."""
    assert len(SwarmTopology) == 4


# ── forge_models: AgentRole ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [
        (AgentRole.PLANNER, "planner"),
        (AgentRole.CODER, "coder"),
        (AgentRole.TESTER, "tester"),
        (AgentRole.REVIEWER, "reviewer"),
        (AgentRole.INTEGRATOR, "integrator"),
    ],
)
def test_agent_role_values(member: AgentRole, value: str) -> None:
    """Each AgentRole member maps to the expected string."""
    assert member.value == value


def test_agent_role_has_exactly_five_members() -> None:
    """AgentRole must have exactly 5 members."""
    assert len(AgentRole) == 5


# ── forge_models: TaskStatus ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [
        (TaskStatus.PENDING, "pending"),
        (TaskStatus.IN_PROGRESS, "in_progress"),
        (TaskStatus.COMPLETED, "completed"),
        (TaskStatus.FAILED, "failed"),
        (TaskStatus.SKIPPED, "skipped"),
    ],
)
def test_task_status_values(member: TaskStatus, value: str) -> None:
    """Each TaskStatus member maps to the expected string."""
    assert member.value == value


def test_task_status_has_exactly_five_members() -> None:
    """TaskStatus must have exactly 5 members."""
    assert len(TaskStatus) == 5


# ── forge_models: Task ───────────────────────────────────────────────────────


def test_task_valid_instantiation() -> None:
    """A Task with all required fields should be created successfully."""
    task = Task(
        module_name="auth_service",
        description="Implement authentication module",
        estimated_complexity=5,
    )
    assert task.module_name == "auth_service"
    assert task.description == "Implement authentication module"
    assert task.estimated_complexity == 5
    assert task.task_id  # auto-generated UUID


def test_task_default_status_pending() -> None:
    """Task status defaults to PENDING."""
    task = Task(
        module_name="api",
        description="Build API layer",
        estimated_complexity=3,
    )
    assert task.status == TaskStatus.PENDING


def test_task_default_retry_count_zero() -> None:
    """Task retry_count defaults to 0."""
    task = Task(
        module_name="api",
        description="Build API layer",
        estimated_complexity=3,
    )
    assert task.retry_count == 0


def test_task_default_max_retries_three() -> None:
    """Task max_retries defaults to 3."""
    task = Task(
        module_name="api",
        description="Build API layer",
        estimated_complexity=3,
    )
    assert task.max_retries == 3


@pytest.mark.parametrize("complexity", [1, 5, 10])
def test_task_complexity_valid_bounds(complexity: int) -> None:
    """Complexity values at boundaries (1, 5, 10) are valid."""
    task = Task(
        module_name="m",
        description="d",
        estimated_complexity=complexity,
    )
    assert task.estimated_complexity == complexity


@pytest.mark.parametrize("complexity", [0, -1, 11, 100])
def test_task_complexity_invalid_raises(complexity: int) -> None:
    """Complexity values outside 1-10 raise ValidationError."""
    with pytest.raises(ValidationError, match="estimated_complexity must be between 1 and 10"):
        Task(
            module_name="m",
            description="d",
            estimated_complexity=complexity,
        )


def test_task_dependencies_default_empty() -> None:
    """Task dependencies defaults to empty list."""
    task = Task(module_name="m", description="d", estimated_complexity=1)
    assert task.dependencies == []


def test_task_assigned_agent_default_none() -> None:
    """Task assigned_agent defaults to None."""
    task = Task(module_name="m", description="d", estimated_complexity=1)
    assert task.assigned_agent is None


# ── forge_models: TaskGraph ──────────────────────────────────────────────────


def test_task_graph_valid_instantiation() -> None:
    """TaskGraph with a list of tasks should be created successfully."""
    t = Task(module_name="m", description="d", estimated_complexity=3)
    graph = TaskGraph(tasks=[t], total_estimated_complexity=3)
    assert len(graph.tasks) == 1
    assert graph.total_estimated_complexity == 3


def test_task_graph_default_topology_hierarchical() -> None:
    """TaskGraph topology defaults to HIERARCHICAL."""
    t = Task(module_name="m", description="d", estimated_complexity=2)
    graph = TaskGraph(tasks=[t], total_estimated_complexity=2)
    assert graph.topology == SwarmTopology.HIERARCHICAL


# ── forge_models: CodeModule ─────────────────────────────────────────────────


def test_code_module_valid_instantiation() -> None:
    """CodeModule with all required fields should be created successfully."""
    mod = CodeModule(
        module_path="src/auth.py",
        content="print('hello')",
        language="python",
        loc=1,
    )
    assert mod.module_path == "src/auth.py"
    assert mod.language == "python"
    assert mod.loc == 1
    assert mod.test_file_path is None


def test_code_module_with_test_file() -> None:
    """CodeModule can include an optional test_file_path."""
    mod = CodeModule(
        module_path="src/auth.py",
        content="code",
        language="python",
        loc=10,
        test_file_path="tests/test_auth.py",
    )
    assert mod.test_file_path == "tests/test_auth.py"


# ── forge_models: ReviewVerdict ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [
        (ReviewVerdict.PASS, "pass"),
        (ReviewVerdict.FAIL, "fail"),
        (ReviewVerdict.PASS_WITH_SUGGESTIONS, "pass_with_suggestions"),
    ],
)
def test_review_verdict_values(member: ReviewVerdict, value: str) -> None:
    """Each ReviewVerdict member maps to the expected string."""
    assert member.value == value


def test_review_verdict_has_exactly_three_members() -> None:
    """ReviewVerdict must have exactly 3 members."""
    assert len(ReviewVerdict) == 3


# ── forge_models: AgentOutput ────────────────────────────────────────────────


def test_agent_output_success_case() -> None:
    """AgentOutput for a successful agent execution."""
    output = AgentOutput(
        agent_role=AgentRole.CODER,
        task_id="task-123",
        success=True,
        tokens_used=5000,
        execution_time_seconds=12.5,
    )
    assert output.success is True
    assert output.error is None
    assert output.output_modules == []
    assert output.retry_count == 0


def test_agent_output_failure_with_structured_error() -> None:
    """AgentOutput for a failed agent execution includes a StructuredError."""
    err = StructuredError(
        error_category=ErrorCategory.TRANSIENT,
        is_retryable=True,
        message="Timeout during code generation",
    )
    output = AgentOutput(
        agent_role=AgentRole.CODER,
        task_id="task-456",
        success=False,
        error=err,
        tokens_used=1000,
        execution_time_seconds=30.0,
        retry_count=2,
    )
    assert output.success is False
    assert output.error is not None
    assert output.error.is_retryable is True
    assert output.retry_count == 2


# ── forge_models: ForgeOutput ────────────────────────────────────────────────


def _make_code_module() -> CodeModule:
    return CodeModule(
        module_path="src/main.py",
        content="# main",
        language="python",
        loc=1,
    )


def test_forge_output_full_instantiation() -> None:
    """ForgeOutput with all fields should be created successfully."""
    mod = _make_code_module()
    forge = ForgeOutput(
        code_modules=[mod],
        test_results={"test_main": True},
        review_verdict=ReviewVerdict.PASS,
        quality_score=85.0,
        total_tokens_used=20000,
        total_retries=1,
        topology_used=SwarmTopology.HIERARCHICAL,
    )
    assert forge.quality_score == 85.0
    assert forge.review_verdict == ReviewVerdict.PASS
    assert forge.total_retries == 1
    assert forge.completed_at is not None


@pytest.mark.parametrize("score", [0.0, 50.0, 100.0])
def test_forge_output_quality_score_valid_bounds(score: float) -> None:
    """Quality score at boundaries (0, 50, 100) are valid."""
    forge = ForgeOutput(
        code_modules=[],
        test_results={},
        review_verdict=ReviewVerdict.PASS,
        quality_score=score,
        total_tokens_used=0,
        total_retries=0,
        topology_used=SwarmTopology.SEQUENTIAL,
    )
    assert forge.quality_score == score


@pytest.mark.parametrize("score", [-0.1, -10.0, 100.1, 200.0])
def test_forge_output_quality_score_invalid_raises(score: float) -> None:
    """Quality score outside 0-100 raises ValidationError."""
    with pytest.raises(ValidationError, match=r"quality_score must be between 0\.0 and 100\.0"):
        ForgeOutput(
            code_modules=[],
            test_results={},
            review_verdict=ReviewVerdict.PASS,
            quality_score=score,
            total_tokens_used=0,
            total_retries=0,
            topology_used=SwarmTopology.SEQUENTIAL,
        )


# ── publisher_models: CommitPhase ────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [
        (CommitPhase.SCAFFOLDING, "scaffolding"),
        (CommitPhase.CORE_MODULES, "core_modules"),
        (CommitPhase.TESTS, "tests"),
        (CommitPhase.ADRS, "adrs"),
        (CommitPhase.DOCS, "docs"),
        (CommitPhase.CI_CD, "ci_cd"),
        (CommitPhase.POLISH, "polish"),
    ],
)
def test_commit_phase_values(member: CommitPhase, value: str) -> None:
    """Each CommitPhase member maps to the expected string."""
    assert member.value == value


def test_commit_phase_has_exactly_seven_members() -> None:
    """CommitPhase must have exactly 7 members."""
    assert len(CommitPhase) == 7


# ── publisher_models: CommitEntry ────────────────────────────────────────────


def test_commit_entry_valid_instantiation() -> None:
    """CommitEntry with all required fields should be created successfully."""
    entry = CommitEntry(
        message="feat(auth): add login endpoint",
        files=["src/auth.py", "tests/test_auth.py"],
        phase=CommitPhase.CORE_MODULES,
        timestamp_offset_hours=24.0,
    )
    assert entry.message == "feat(auth): add login endpoint"
    assert len(entry.files) == 2
    assert entry.phase == CommitPhase.CORE_MODULES
    assert entry.timestamp_offset_hours == 24.0


# ── publisher_models: CommitPlan ─────────────────────────────────────────────


def test_commit_plan_with_entries() -> None:
    """CommitPlan with a list of CommitEntry objects."""
    entry = CommitEntry(
        message="feat: scaffold",
        files=["README.md"],
        phase=CommitPhase.SCAFFOLDING,
        timestamp_offset_hours=0.0,
    )
    plan = CommitPlan(commits=[entry], total_commits=1)
    assert len(plan.commits) == 1
    assert plan.total_commits == 1


def test_commit_plan_default_spread_days_five() -> None:
    """CommitPlan spread_days defaults to 5."""
    plan = CommitPlan(commits=[], total_commits=0)
    assert plan.spread_days == 5


# ── publisher_models: RepoConfig ─────────────────────────────────────────────


def test_repo_config_default_private_true() -> None:
    """RepoConfig private defaults to True per security rules."""
    config = RepoConfig(
        repo_name="my-project",
        description="A cool project",
        topics=["python", "ai"],
    )
    assert config.private is True


def test_repo_config_default_branch_main() -> None:
    """RepoConfig default_branch defaults to 'main'."""
    config = RepoConfig(
        repo_name="my-project",
        description="desc",
        topics=[],
    )
    assert config.default_branch == "main"


def test_repo_config_defaults() -> None:
    """RepoConfig has sensible defaults for has_wiki and has_issues."""
    config = RepoConfig(
        repo_name="my-project",
        description="desc",
        topics=[],
    )
    assert config.has_wiki is False
    assert config.has_issues is True


# ── publisher_models: PublishResult ──────────────────────────────────────────


def _make_repo_config() -> RepoConfig:
    return RepoConfig(
        repo_name="test-repo",
        description="Test",
        topics=["test"],
    )


def _make_commit_plan() -> CommitPlan:
    return CommitPlan(commits=[], total_commits=0)


def test_publish_result_full_instantiation() -> None:
    """PublishResult with all fields should be created successfully."""
    result = PublishResult(
        repo_url="https://github.com/user/test-repo",
        commit_shas=["abc123", "def456"],
        readme_url="https://github.com/user/test-repo/blob/main/README.md",
        repo_config=_make_repo_config(),
        commit_plan=_make_commit_plan(),
    )
    assert result.repo_url == "https://github.com/user/test-repo"
    assert len(result.commit_shas) == 2
    assert result.publish_id  # auto-generated UUID


def test_publish_result_default_published_at() -> None:
    """PublishResult published_at defaults to current UTC time."""
    before = datetime.now(UTC)
    result = PublishResult(
        repo_url="https://github.com/user/repo",
        commit_shas=[],
        readme_url="https://github.com/user/repo/blob/main/README.md",
        repo_config=_make_repo_config(),
        commit_plan=_make_commit_plan(),
    )
    after = datetime.now(UTC)
    assert before <= result.published_at <= after


# ── content_models: ContentFormat ────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [
        (ContentFormat.YOUTUBE_SCRIPT, "youtube_script"),
        (ContentFormat.BLOG_POST, "blog_post"),
        (ContentFormat.LINKEDIN_CAROUSEL, "linkedin_carousel"),
        (ContentFormat.TWITTER_THREAD, "twitter_thread"),
        (ContentFormat.PROJECT_WALKTHROUGH, "project_walkthrough"),
    ],
)
def test_content_format_values(member: ContentFormat, value: str) -> None:
    """Each ContentFormat member maps to the expected string."""
    assert member.value == value


def test_content_format_has_exactly_five_members() -> None:
    """ContentFormat must have exactly 5 members."""
    assert len(ContentFormat) == 5


# ── content_models: ContentOutput ────────────────────────────────────────────


def test_content_output_valid_instantiation() -> None:
    """ContentOutput with all required fields should be created successfully."""
    output = ContentOutput(
        format=ContentFormat.BLOG_POST,
        title="Building an AI Pipeline",
        content="This is the blog post content...",
        word_count=2500,
        target_platform="Medium",
        seo_keywords=["ai", "pipeline", "portfolio"],
    )
    assert output.format == ContentFormat.BLOG_POST
    assert output.title == "Building an AI Pipeline"
    assert output.word_count == 2500
    assert output.target_platform == "Medium"
    assert len(output.seo_keywords) == 3
    assert output.content_id  # auto-generated UUID


def test_content_output_default_created_at() -> None:
    """ContentOutput created_at defaults to current UTC time."""
    before = datetime.now(UTC)
    output = ContentOutput(
        format=ContentFormat.TWITTER_THREAD,
        title="Thread",
        content="content",
        word_count=100,
        target_platform="Twitter",
        seo_keywords=[],
    )
    after = datetime.now(UTC)
    assert before <= output.created_at <= after


# ── memory_models: VerdictOutcome ────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [
        (VerdictOutcome.PASS, "pass"),
        (VerdictOutcome.FAIL, "fail"),
        (VerdictOutcome.PARTIAL, "partial"),
    ],
)
def test_verdict_outcome_values(member: VerdictOutcome, value: str) -> None:
    """Each VerdictOutcome member maps to the expected string."""
    assert member.value == value


def test_verdict_outcome_has_exactly_three_members() -> None:
    """VerdictOutcome must have exactly 3 members."""
    assert len(VerdictOutcome) == 3


# ── memory_models: JudgeVerdict ──────────────────────────────────────────────


def test_judge_verdict_valid_instantiation() -> None:
    """JudgeVerdict with all required fields should be created successfully."""
    verdict = JudgeVerdict(
        run_id="run-001",
        outcome=VerdictOutcome.PASS,
        sandbox_passed=True,
        quality_score=85.0,
        retry_count_total=1,
        api_cost_gbp=3.50,
        generation_time_seconds=120.0,
    )
    assert verdict.run_id == "run-001"
    assert verdict.outcome == VerdictOutcome.PASS
    assert verdict.sandbox_passed is True
    assert verdict.quality_score == 85.0
    assert verdict.api_cost_gbp == 3.50
    assert verdict.verdict_id  # auto-generated UUID
    assert verdict.failure_reasons == []


def test_judge_verdict_quality_score_at_bounds() -> None:
    """JudgeVerdict accepts quality_score at 0 and 100."""
    for score in [0.0, 100.0]:
        verdict = JudgeVerdict(
            run_id="run",
            outcome=VerdictOutcome.PASS,
            sandbox_passed=True,
            quality_score=score,
            retry_count_total=0,
            api_cost_gbp=0.0,
            generation_time_seconds=0.0,
        )
        assert verdict.quality_score == score


def test_judge_verdict_cost_in_gbp() -> None:
    """JudgeVerdict api_cost_gbp accepts float values representing GBP."""
    verdict = JudgeVerdict(
        run_id="run",
        outcome=VerdictOutcome.FAIL,
        sandbox_passed=False,
        quality_score=30.0,
        retry_count_total=3,
        api_cost_gbp=12.75,
        generation_time_seconds=300.0,
        failure_reasons=["tests failed", "lint errors"],
    )
    assert verdict.api_cost_gbp == 12.75
    assert len(verdict.failure_reasons) == 2


# ── memory_models: DistilledPattern ──────────────────────────────────────────


def test_distilled_pattern_valid_instantiation() -> None:
    """DistilledPattern with all required fields should be created successfully."""
    pattern = DistilledPattern(
        pattern_text="Use factory pattern for service initialization",
        source_verdicts=["v1", "v2", "v3"],
        confidence=82.5,
        tech_stack_tags=["python", "fastapi"],
        success_rate=90.0,
        sample_count=10,
    )
    assert pattern.pattern_text == "Use factory pattern for service initialization"
    assert len(pattern.source_verdicts) == 3
    assert pattern.confidence == 82.5
    assert pattern.success_rate == 90.0
    assert pattern.sample_count == 10
    assert pattern.pattern_id  # auto-generated UUID


@pytest.mark.parametrize("value", [0.0, 50.0, 100.0])
def test_distilled_pattern_confidence_valid_bounds(value: float) -> None:
    """DistilledPattern confidence accepts values at boundaries."""
    pattern = DistilledPattern(
        pattern_text="p",
        source_verdicts=[],
        confidence=value,
        tech_stack_tags=[],
        success_rate=50.0,
        sample_count=1,
    )
    assert pattern.confidence == value


@pytest.mark.parametrize("value", [0.0, 50.0, 100.0])
def test_distilled_pattern_success_rate_valid_bounds(value: float) -> None:
    """DistilledPattern success_rate accepts values at boundaries."""
    pattern = DistilledPattern(
        pattern_text="p",
        source_verdicts=[],
        confidence=50.0,
        tech_stack_tags=[],
        success_rate=value,
        sample_count=1,
    )
    assert pattern.success_rate == value


# ── memory_models: MemoryRecord ──────────────────────────────────────────────


def test_memory_record_valid_without_embedding() -> None:
    """MemoryRecord without embedding or expires_at."""
    record = MemoryRecord(
        record_type="company_profile",
        data={"name": "Acme Corp", "tech_stack": ["python"]},
    )
    assert record.record_type == "company_profile"
    assert record.embedding is None
    assert record.expires_at is None
    assert record.record_id  # auto-generated UUID


def test_memory_record_valid_with_embedding_and_expiry() -> None:
    """MemoryRecord with embedding and expires_at set."""
    expires = datetime(2026, 6, 1, tzinfo=UTC)
    record = MemoryRecord(
        record_type="reasoning_pattern",
        data={"strategy": "use caching"},
        embedding=[0.1, 0.2, 0.3],
        expires_at=expires,
    )
    assert record.embedding == [0.1, 0.2, 0.3]
    assert record.expires_at == expires


# ── memory_models: ReasoningBankQuery ────────────────────────────────────────


def test_reasoning_bank_query_defaults() -> None:
    """ReasoningBankQuery defaults: top_k=5, min_confidence=50.0."""
    query = ReasoningBankQuery(query_text="fastapi auth patterns")
    assert query.top_k == 5
    assert query.min_confidence == 50.0
    assert query.tech_stack_filter == []


def test_reasoning_bank_query_custom_values() -> None:
    """ReasoningBankQuery with custom top_k and min_confidence."""
    query = ReasoningBankQuery(
        query_text="react state management",
        tech_stack_filter=["react", "typescript"],
        top_k=10,
        min_confidence=75.0,
    )
    assert query.top_k == 10
    assert query.min_confidence == 75.0
    assert len(query.tech_stack_filter) == 2


# ── config_models: ModelTaskMapping ──────────────────────────────────────────


def test_model_task_mapping_valid_instantiation() -> None:
    """ModelTaskMapping with all required fields should be created successfully."""
    mapping = ModelTaskMapping(
        task_name="architecture",
        model_id="claude-opus-4-6",
    )
    assert mapping.task_name == "architecture"
    assert mapping.model_id == "claude-opus-4-6"
    assert mapping.fallback_model_id is None
    assert mapping.tool_choice is None


def test_model_task_mapping_with_fallback_and_tool_choice() -> None:
    """ModelTaskMapping with fallback and tool_choice set."""
    mapping = ModelTaskMapping(
        task_name="code_gen",
        model_id="claude-sonnet-4-6",
        fallback_model_id="gpt-4o",
        tool_choice="auto",
    )
    assert mapping.fallback_model_id == "gpt-4o"
    assert mapping.tool_choice == "auto"


# ── config_models: SandboxConfig ─────────────────────────────────────────────


def test_sandbox_config_defaults_match_architecture() -> None:
    """SandboxConfig defaults match architecture spec: 4 CPU, 8GB, 20GB, 30min, pool 3."""
    config = SandboxConfig()
    assert config.base_image == "letsbuild/sandbox:latest"
    assert config.cpu_limit == 4
    assert config.memory_limit_gb == 8
    assert config.disk_limit_gb == 20
    assert config.lifetime_minutes == 30
    assert config.pool_size == 3


def test_sandbox_config_custom_values() -> None:
    """SandboxConfig with custom overrides."""
    config = SandboxConfig(
        base_image="custom/image:v2",
        cpu_limit=8,
        memory_limit_gb=16,
        disk_limit_gb=50,
        lifetime_minutes=60,
        pool_size=5,
    )
    assert config.cpu_limit == 8
    assert config.memory_limit_gb == 16


# ── config_models: SkillConfig ───────────────────────────────────────────────


def test_skill_config_valid_instantiation() -> None:
    """SkillConfig with all required fields should be created successfully."""
    config = SkillConfig(
        name="fullstack",
        display_name="Full-Stack Web Application",
        category="project",
        role_categories=["full_stack_engineer", "backend_engineer"],
        seniority_range=["junior", "mid", "senior", "staff"],
        tech_stacks_primary=["React", "FastAPI"],
        complexity_range=[3, 8],
        estimated_loc=[800, 3000],
    )
    assert config.name == "fullstack"
    assert config.display_name == "Full-Stack Web Application"
    assert config.category == "project"
    assert len(config.role_categories) == 2
    assert config.topology == "hierarchical"
    assert config.tech_stacks_alternatives == []


# ── config_models: NotificationConfig ────────────────────────────────────────


def test_notification_config_defaults() -> None:
    """NotificationConfig websocket_enabled=True, others=False by default."""
    config = NotificationConfig()
    assert config.websocket_enabled is True
    assert config.telegram_enabled is False
    assert config.slack_enabled is False
    assert config.discord_enabled is False


# ── config_models: AppConfig ─────────────────────────────────────────────────


def test_app_config_defaults() -> None:
    """AppConfig defaults: budget 50, quality 70, retries 2."""
    config = AppConfig()
    assert config.budget_limit_gbp == 50.0
    assert config.quality_threshold == 70.0
    assert config.max_retries_per_layer == 2
    assert config.project_name == "letsbuild"
    assert config.anthropic_model_default == "claude-sonnet-4-6"
    assert config.model_mappings == []


def test_app_config_nested_defaults() -> None:
    """AppConfig sandbox and notifications use their own defaults."""
    config = AppConfig()
    assert config.sandbox.cpu_limit == 4
    assert config.sandbox.pool_size == 3
    assert config.notifications.websocket_enabled is True
    assert config.notifications.telegram_enabled is False


def test_app_config_custom_values() -> None:
    """AppConfig with custom overrides."""
    config = AppConfig(
        budget_limit_gbp=100.0,
        quality_threshold=85.0,
        max_retries_per_layer=5,
        sandbox=SandboxConfig(cpu_limit=8),
    )
    assert config.budget_limit_gbp == 100.0
    assert config.quality_threshold == 85.0
    assert config.max_retries_per_layer == 5
    assert config.sandbox.cpu_limit == 8
