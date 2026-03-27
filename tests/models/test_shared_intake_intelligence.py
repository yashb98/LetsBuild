"""Comprehensive tests for shared, intake, and intelligence models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.intelligence_models import (
    CompanyProfile,
    DataSource,
    EngineeringCulture,
    ResearchResult,
    SubAgentResult,
    SubAgentType,
)
from letsbuild.models.shared import (
    BudgetInfo,
    ErrorCategory,
    GateResult,
    ModelConfig,
    PipelineMetrics,
    StructuredError,
)

# ---------------------------------------------------------------------------
# shared.py — StructuredError
# ---------------------------------------------------------------------------


class TestStructuredError:
    """Tests for StructuredError model."""

    def test_structured_error_instantiation_all_fields(self) -> None:
        """Full instantiation with every field explicitly set."""
        err = StructuredError(
            error_id="abc-123",
            error_category=ErrorCategory.TRANSIENT,
            is_retryable=True,
            message="Connection timed out",
            partial_results={"key": "value"},
            attempted_query="SELECT 1",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert err.error_id == "abc-123"
        assert err.error_category == ErrorCategory.TRANSIENT
        assert err.is_retryable is True
        assert err.message == "Connection timed out"
        assert err.partial_results == {"key": "value"}
        assert err.attempted_query == "SELECT 1"
        assert err.timestamp == datetime(2026, 1, 1, tzinfo=UTC)

    def test_structured_error_default_uuid_generated(self) -> None:
        """error_id should be auto-generated as a UUID string."""
        err = StructuredError(
            error_category=ErrorCategory.VALIDATION,
            is_retryable=False,
            message="Bad input",
        )
        assert isinstance(err.error_id, str)
        assert len(err.error_id) == 36  # UUID4 format

    def test_structured_error_default_timestamp_generated(self) -> None:
        """timestamp should default to approximately now (UTC)."""
        before = datetime.now(UTC)
        err = StructuredError(
            error_category=ErrorCategory.BUSINESS,
            is_retryable=False,
            message="Not allowed",
        )
        after = datetime.now(UTC)
        assert before <= err.timestamp <= after

    @pytest.mark.parametrize(
        "category",
        list(ErrorCategory),
        ids=[c.value for c in ErrorCategory],
    )
    def test_structured_error_all_error_categories(self, category: ErrorCategory) -> None:
        """Every ErrorCategory value should be accepted."""
        err = StructuredError(
            error_category=category,
            is_retryable=True,
            message=f"Error with {category.value}",
        )
        assert err.error_category == category

    def test_structured_error_wrong_type_rejected(self) -> None:
        """Strict mode should reject wrong types."""
        with pytest.raises(ValidationError):
            StructuredError(
                error_category="not_a_valid_category",  # type: ignore[arg-type]
                is_retryable="yes",  # type: ignore[arg-type]
                message=123,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# shared.py — GateResult
# ---------------------------------------------------------------------------


class TestGateResult:
    """Tests for GateResult model."""

    def test_gate_result_passed(self) -> None:
        """Gate that passed with all fields populated."""
        result = GateResult(
            passed=True,
            reason="All checks passed",
            blocking=True,
            gate_name="PublishGate",
        )
        assert result.passed is True
        assert result.reason == "All checks passed"
        assert result.blocking is True
        assert result.gate_name == "PublishGate"
        assert isinstance(result.timestamp, datetime)

    def test_gate_result_failed(self) -> None:
        """Gate that failed."""
        result = GateResult(
            passed=False,
            reason="Quality score too low",
            blocking=True,
            gate_name="QualityGate",
        )
        assert result.passed is False
        assert result.blocking is True

    def test_gate_result_non_blocking_failure(self) -> None:
        """Non-blocking gate failure should still record the result."""
        result = GateResult(
            passed=False,
            reason="Minor style issue",
            blocking=False,
            gate_name="StyleGate",
        )
        assert result.passed is False
        assert result.blocking is False


# ---------------------------------------------------------------------------
# shared.py — PipelineMetrics
# ---------------------------------------------------------------------------


class TestPipelineMetrics:
    """Tests for PipelineMetrics model."""

    def test_pipeline_metrics_defaults_are_zero(self) -> None:
        """All numeric defaults should be zero."""
        metrics = PipelineMetrics()
        assert metrics.total_duration_seconds == 0.0
        assert metrics.total_tokens_used == 0
        assert metrics.total_api_cost_gbp == 0.0
        assert metrics.quality_score == 0.0
        assert metrics.layer_durations == {}
        assert metrics.retries_by_layer == {}

    def test_pipeline_metrics_layer_durations(self) -> None:
        """layer_durations dict works correctly."""
        metrics = PipelineMetrics(
            layer_durations={"intake": 1.5, "intelligence": 3.2, "forge": 12.0},
            retries_by_layer={"forge": 2},
        )
        assert metrics.layer_durations["intake"] == 1.5
        assert metrics.layer_durations["forge"] == 12.0
        assert metrics.retries_by_layer["forge"] == 2


# ---------------------------------------------------------------------------
# shared.py — BudgetInfo
# ---------------------------------------------------------------------------


class TestBudgetInfo:
    """Tests for BudgetInfo model."""

    def test_budget_info_defaults(self) -> None:
        """Default budget is 50 GBP with nothing spent."""
        budget = BudgetInfo()
        assert budget.budget_limit_gbp == 50.0
        assert budget.spent_gbp == 0.0
        assert budget.remaining_gbp == 50.0
        assert budget.cost_by_model == {}

    def test_record_cost_updates_correctly(self) -> None:
        """record_cost should update spent, remaining, and cost_by_model."""
        budget = BudgetInfo()
        budget.record_cost("claude-sonnet-4-6", 5.0)
        assert budget.spent_gbp == 5.0
        assert budget.remaining_gbp == 45.0
        assert budget.cost_by_model["claude-sonnet-4-6"] == 5.0

    def test_record_cost_accumulates(self) -> None:
        """Multiple record_cost calls for the same model should accumulate."""
        budget = BudgetInfo()
        budget.record_cost("claude-sonnet-4-6", 3.0)
        budget.record_cost("claude-sonnet-4-6", 2.0)
        assert budget.spent_gbp == 5.0
        assert budget.remaining_gbp == 45.0
        assert budget.cost_by_model["claude-sonnet-4-6"] == 5.0

    def test_record_cost_multiple_models(self) -> None:
        """record_cost tracks different models separately."""
        budget = BudgetInfo()
        budget.record_cost("claude-sonnet-4-6", 3.0)
        budget.record_cost("claude-opus-4-6", 10.0)
        assert budget.cost_by_model["claude-sonnet-4-6"] == 3.0
        assert budget.cost_by_model["claude-opus-4-6"] == 10.0
        assert budget.spent_gbp == 13.0

    def test_is_over_budget_false(self) -> None:
        """is_over_budget returns False when under budget."""
        budget = BudgetInfo()
        budget.record_cost("claude-sonnet-4-6", 10.0)
        assert budget.is_over_budget() is False

    def test_is_over_budget_true(self) -> None:
        """is_over_budget returns True when over budget."""
        budget = BudgetInfo()
        budget.record_cost("claude-sonnet-4-6", 51.0)
        assert budget.is_over_budget() is True

    def test_is_over_budget_at_exact_limit(self) -> None:
        """Spending exactly the limit should NOT be over budget."""
        budget = BudgetInfo()
        budget.record_cost("claude-sonnet-4-6", 50.0)
        assert budget.is_over_budget() is False


# ---------------------------------------------------------------------------
# shared.py — ModelConfig
# ---------------------------------------------------------------------------


class TestModelConfig:
    """Tests for ModelConfig model."""

    def test_model_config_full_instantiation(self) -> None:
        """All fields can be set explicitly."""
        cfg = ModelConfig(
            model_id="claude-sonnet-4-6",
            max_tokens=8192,
            temperature=0.7,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        )
        assert cfg.model_id == "claude-sonnet-4-6"
        assert cfg.max_tokens == 8192
        assert cfg.temperature == 0.7
        assert cfg.cost_per_1k_input == 0.003
        assert cfg.cost_per_1k_output == 0.015

    def test_model_config_defaults(self) -> None:
        """Defaults should apply for optional fields."""
        cfg = ModelConfig(model_id="claude-haiku-3")
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.0
        assert cfg.cost_per_1k_input == 0.0
        assert cfg.cost_per_1k_output == 0.0

    def test_model_config_strict_rejects_wrong_types(self) -> None:
        """Strict mode rejects wrong types."""
        with pytest.raises(ValidationError):
            ModelConfig(model_id=12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# intake_models.py — RoleCategory
# ---------------------------------------------------------------------------


class TestRoleCategory:
    """Tests for RoleCategory enum."""

    @pytest.mark.parametrize(
        "member",
        list(RoleCategory),
        ids=[rc.name for rc in RoleCategory],
    )
    def test_role_category_all_values_accessible(self, member: RoleCategory) -> None:
        """Every enum member should be accessible and have a string value."""
        assert isinstance(member.value, str)

    def test_role_category_string_comparison(self) -> None:
        """RoleCategory values should compare equal to their string representation."""
        assert RoleCategory.FULL_STACK == "full_stack_engineer"
        assert RoleCategory.ML_ENGINEER == "ml_engineer"
        assert RoleCategory.OTHER == "other"

    def test_role_category_count(self) -> None:
        """There should be 16 role categories."""
        assert len(RoleCategory) == 16


# ---------------------------------------------------------------------------
# intake_models.py — SeniorityLevel
# ---------------------------------------------------------------------------


class TestSeniorityLevel:
    """Tests for SeniorityLevel enum."""

    @pytest.mark.parametrize(
        "member",
        list(SeniorityLevel),
        ids=[sl.name for sl in SeniorityLevel],
    )
    def test_seniority_level_all_values_accessible(self, member: SeniorityLevel) -> None:
        """Every enum member should be accessible."""
        assert isinstance(member.value, str)

    def test_seniority_level_count(self) -> None:
        """There should be 5 seniority levels."""
        assert len(SeniorityLevel) == 5


# ---------------------------------------------------------------------------
# intake_models.py — Skill
# ---------------------------------------------------------------------------


class TestSkill:
    """Tests for Skill model."""

    def test_skill_valid_instantiation(self) -> None:
        """Skill with all fields."""
        skill = Skill(
            name="Python",
            category="language",
            confidence=95.0,
            aliases=["python3", "py"],
            is_primary=True,
        )
        assert skill.name == "Python"
        assert skill.category == "language"
        assert skill.confidence == 95.0
        assert skill.aliases == ["python3", "py"]
        assert skill.is_primary is True

    def test_skill_default_aliases_empty(self) -> None:
        """Default aliases should be an empty list."""
        skill = Skill(name="Kubernetes", category="tool")
        assert skill.aliases == []
        assert skill.is_primary is False
        assert skill.confidence == 100.0

    def test_skill_confidence_lower_bound(self) -> None:
        """Confidence of 0.0 should be accepted."""
        skill = Skill(name="Rust", category="language", confidence=0.0)
        assert skill.confidence == 0.0

    def test_skill_confidence_upper_bound(self) -> None:
        """Confidence of 100.0 should be accepted."""
        skill = Skill(name="Go", category="language", confidence=100.0)
        assert skill.confidence == 100.0

    def test_skill_confidence_below_zero_rejected(self) -> None:
        """Confidence below 0 should be rejected."""
        with pytest.raises(ValidationError):
            Skill(name="Java", category="language", confidence=-1.0)

    def test_skill_confidence_above_hundred_rejected(self) -> None:
        """Confidence above 100 should be rejected."""
        with pytest.raises(ValidationError):
            Skill(name="Java", category="language", confidence=101.0)


# ---------------------------------------------------------------------------
# intake_models.py — TechStack
# ---------------------------------------------------------------------------


class TestTechStack:
    """Tests for TechStack model."""

    def test_tech_stack_default_empty_lists(self) -> None:
        """All lists default to empty."""
        ts = TechStack()
        assert ts.languages == []
        assert ts.frameworks == []
        assert ts.databases == []
        assert ts.cloud_providers == []
        assert ts.tools == []
        assert ts.infrastructure == []

    def test_tech_stack_populated_lists(self) -> None:
        """All lists can be populated."""
        ts = TechStack(
            languages=["python", "typescript"],
            frameworks=["fastapi", "react"],
            databases=["postgresql"],
            cloud_providers=["aws"],
            tools=["docker"],
            infrastructure=["kubernetes"],
        )
        assert "python" in ts.languages
        assert "react" in ts.frameworks

    def test_tech_stack_enforce_lowercase(self) -> None:
        """Mixed-case items should be lowered by the validator."""
        ts = TechStack(
            languages=["Python", "TypeScript"],
            frameworks=["FastAPI"],
            databases=["PostgreSQL"],
            cloud_providers=["AWS"],
            tools=["Docker"],
            infrastructure=["Kubernetes"],
        )
        assert ts.languages == ["python", "typescript"]
        assert ts.frameworks == ["fastapi"]
        assert ts.databases == ["postgresql"]
        assert ts.cloud_providers == ["aws"]
        assert ts.tools == ["docker"]
        assert ts.infrastructure == ["kubernetes"]


# ---------------------------------------------------------------------------
# intake_models.py — JDAnalysis
# ---------------------------------------------------------------------------


class TestJDAnalysis:
    """Tests for JDAnalysis model."""

    def _make_jd(self, **overrides: object) -> JDAnalysis:
        """Helper to create a minimal valid JDAnalysis."""
        defaults: dict[str, object] = {
            "role_title": "Senior Backend Engineer",
            "role_category": RoleCategory.BACKEND,
            "seniority": SeniorityLevel.SENIOR,
            "raw_text": "We are looking for a Senior Backend Engineer...",
        }
        defaults.update(overrides)
        return JDAnalysis(**defaults)  # type: ignore[arg-type]

    def test_jd_analysis_full_instantiation(self) -> None:
        """Full instantiation with all optional fields populated."""
        jd = self._make_jd(
            company_name="Acme Corp",
            company_url="https://acme.com",
            required_skills=[Skill(name="Python", category="language")],
            preferred_skills=[Skill(name="Go", category="language")],
            tech_stack=TechStack(languages=["python", "go"]),
            domain_keywords=["fintech", "real-time"],
            key_responsibilities=["Design APIs", "Lead team"],
            years_experience_min=5,
            years_experience_max=10,
            location="London",
            remote_policy="hybrid",
            salary_min_gbp=80000.00,
            salary_max_gbp=120000.00,
            source_url="https://jobs.example.com/123",
        )
        assert jd.company_name == "Acme Corp"
        assert jd.salary_min_gbp == 80000.00
        assert jd.salary_max_gbp == 120000.00
        assert len(jd.required_skills) == 1
        assert len(jd.preferred_skills) == 1

    def test_jd_analysis_default_uuid_generated(self) -> None:
        """jd_id should auto-generate as UUID4."""
        jd = self._make_jd()
        assert isinstance(jd.jd_id, str)
        assert len(jd.jd_id) == 36

    def test_jd_analysis_default_timestamp_generated(self) -> None:
        """parsed_at should default to approximately now UTC."""
        before = datetime.now(UTC)
        jd = self._make_jd()
        after = datetime.now(UTC)
        assert before <= jd.parsed_at <= after

    def test_jd_analysis_salary_as_gbp_floats(self) -> None:
        """Salary fields are floats representing GBP amounts."""
        jd = self._make_jd(salary_min_gbp=65000.50, salary_max_gbp=95000.75)
        assert isinstance(jd.salary_min_gbp, float)
        assert isinstance(jd.salary_max_gbp, float)

    def test_jd_analysis_role_category_other_requires_detail(self) -> None:
        """role_category OTHER without detail should raise ValidationError."""
        with pytest.raises(ValidationError, match="role_category_detail must be provided"):
            self._make_jd(role_category=RoleCategory.OTHER)

    def test_jd_analysis_role_category_other_with_detail(self) -> None:
        """role_category OTHER with detail should succeed."""
        jd = self._make_jd(
            role_category=RoleCategory.OTHER,
            role_category_detail="Quantum Computing Researcher",
        )
        assert jd.role_category_detail == "Quantum Computing Researcher"

    def test_jd_analysis_role_category_detail_cleared_for_non_other(self) -> None:
        """role_category_detail is cleared when role_category is not OTHER."""
        jd = self._make_jd(
            role_category=RoleCategory.BACKEND,
            role_category_detail="Should be cleared",
        )
        assert jd.role_category_detail is None

    def test_jd_analysis_experience_min_exceeds_max_rejected(self) -> None:
        """years_experience_min > max should raise ValidationError."""
        with pytest.raises(ValidationError, match="years_experience_min cannot exceed"):
            self._make_jd(years_experience_min=10, years_experience_max=5)

    def test_jd_analysis_salary_min_exceeds_max_rejected(self) -> None:
        """salary_min_gbp > salary_max_gbp should raise ValidationError."""
        with pytest.raises(ValidationError, match="salary_min_gbp cannot exceed"):
            self._make_jd(salary_min_gbp=100000.0, salary_max_gbp=50000.0)

    def test_jd_analysis_json_schema_generation(self) -> None:
        """model_json_schema should return a valid dict with expected fields."""
        schema = JDAnalysis.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        props = schema["properties"]
        assert "role_title" in props
        assert "role_category" in props
        assert "seniority" in props
        assert "required_skills" in props
        assert "tech_stack" in props
        assert "salary_min_gbp" in props
        assert "raw_text" in props

    def test_jd_analysis_negative_salary_rejected(self) -> None:
        """Negative salary should be rejected by ge=0.0 constraint."""
        with pytest.raises(ValidationError):
            self._make_jd(salary_min_gbp=-1.0)

    def test_jd_analysis_negative_experience_rejected(self) -> None:
        """Negative years_experience should be rejected."""
        with pytest.raises(ValidationError):
            self._make_jd(years_experience_min=-1)


# ---------------------------------------------------------------------------
# intelligence_models.py — DataSource
# ---------------------------------------------------------------------------


class TestDataSource:
    """Tests for DataSource model."""

    def test_data_source_instantiation(self) -> None:
        """Full instantiation with all fields."""
        ds = DataSource(
            name="Acme Corp Website",
            url="https://acme.com",
            source_type="website",
            reliability_score=85.0,
        )
        assert ds.name == "Acme Corp Website"
        assert ds.url == "https://acme.com"
        assert ds.source_type == "website"
        assert ds.reliability_score == 85.0
        assert isinstance(ds.retrieved_at, datetime)

    def test_data_source_no_url(self) -> None:
        """URL is optional."""
        ds = DataSource(
            name="Internal Cache",
            source_type="cache",
            reliability_score=100.0,
        )
        assert ds.url is None

    def test_data_source_reliability_lower_bound(self) -> None:
        """reliability_score of 0.0 should be accepted."""
        ds = DataSource(name="Unreliable", source_type="rumor", reliability_score=0.0)
        assert ds.reliability_score == 0.0

    def test_data_source_reliability_upper_bound(self) -> None:
        """reliability_score of 100.0 should be accepted."""
        ds = DataSource(name="Official", source_type="api", reliability_score=100.0)
        assert ds.reliability_score == 100.0

    def test_data_source_reliability_below_zero_rejected(self) -> None:
        """reliability_score below 0 should be rejected."""
        with pytest.raises(ValidationError):
            DataSource(name="Bad", source_type="test", reliability_score=-1.0)

    def test_data_source_reliability_above_hundred_rejected(self) -> None:
        """reliability_score above 100 should be rejected."""
        with pytest.raises(ValidationError):
            DataSource(name="Bad", source_type="test", reliability_score=101.0)


# ---------------------------------------------------------------------------
# intelligence_models.py — SubAgentType
# ---------------------------------------------------------------------------


class TestSubAgentType:
    """Tests for SubAgentType enum."""

    @pytest.mark.parametrize(
        "member",
        list(SubAgentType),
        ids=[sa.name for sa in SubAgentType],
    )
    def test_sub_agent_type_all_values(self, member: SubAgentType) -> None:
        """All 6 sub-agent types should be accessible."""
        assert isinstance(member.value, str)

    def test_sub_agent_type_count(self) -> None:
        """There should be exactly 6 sub-agent types."""
        assert len(SubAgentType) == 6

    def test_sub_agent_type_expected_values(self) -> None:
        """Verify the expected string values."""
        expected = {
            "web_presence",
            "tech_blog",
            "github_org",
            "business_intel",
            "news_monitor",
            "culture_probe",
        }
        actual = {sa.value for sa in SubAgentType}
        assert actual == expected


# ---------------------------------------------------------------------------
# intelligence_models.py — SubAgentResult
# ---------------------------------------------------------------------------


class TestSubAgentResult:
    """Tests for SubAgentResult model."""

    def test_sub_agent_result_success(self) -> None:
        """Successful sub-agent result with data."""
        result = SubAgentResult(
            agent_type=SubAgentType.WEB_PRESENCE,
            success=True,
            data={"homepage": "https://acme.com", "description": "A tech company"},
            data_sources=[
                DataSource(
                    name="Acme Website",
                    source_type="website",
                    reliability_score=90.0,
                )
            ],
            execution_time_seconds=2.5,
        )
        assert result.success is True
        assert result.error is None
        assert len(result.data_sources) == 1
        assert result.execution_time_seconds == 2.5

    def test_sub_agent_result_failure_with_error(self) -> None:
        """Failed sub-agent result with a StructuredError."""
        err = StructuredError(
            error_category=ErrorCategory.TRANSIENT,
            is_retryable=True,
            message="Request timed out",
        )
        result = SubAgentResult(
            agent_type=SubAgentType.TECH_BLOG,
            success=False,
            error=err,
            execution_time_seconds=30.0,
        )
        assert result.success is False
        assert result.error is not None
        assert result.error.error_category == ErrorCategory.TRANSIENT
        assert result.error.is_retryable is True
        assert result.data == {}


# ---------------------------------------------------------------------------
# intelligence_models.py — EngineeringCulture
# ---------------------------------------------------------------------------


class TestEngineeringCulture:
    """Tests for EngineeringCulture model."""

    def test_engineering_culture_full(self) -> None:
        """Full instantiation with all fields."""
        culture = EngineeringCulture(
            open_source_active=True,
            tech_blog_active=True,
            engineering_team_size="50-200",
            development_methodology="scrum",
            key_values=["move fast", "test everything", "code review"],
        )
        assert culture.open_source_active is True
        assert culture.tech_blog_active is True
        assert culture.engineering_team_size == "50-200"
        assert culture.development_methodology == "scrum"
        assert len(culture.key_values) == 3

    def test_engineering_culture_minimal(self) -> None:
        """Minimal instantiation with only required fields."""
        culture = EngineeringCulture(
            open_source_active=False,
            tech_blog_active=False,
        )
        assert culture.engineering_team_size is None
        assert culture.development_methodology is None
        assert culture.key_values == []


# ---------------------------------------------------------------------------
# intelligence_models.py — CompanyProfile
# ---------------------------------------------------------------------------


class TestCompanyProfile:
    """Tests for CompanyProfile model."""

    def _make_profile(self, **overrides: object) -> CompanyProfile:
        """Helper to create a minimal valid CompanyProfile."""
        defaults: dict[str, object] = {
            "company_name": "Acme Corp",
            "confidence_score": 75.0,
        }
        defaults.update(overrides)
        return CompanyProfile(**defaults)  # type: ignore[arg-type]

    def test_company_profile_full_instantiation(self) -> None:
        """Full instantiation with all fields populated."""
        culture = EngineeringCulture(
            open_source_active=True,
            tech_blog_active=True,
        )
        profile = self._make_profile(
            company_url="https://acme.com",
            industry="fintech",
            company_size="enterprise",
            tech_stack_signals=["python", "kubernetes", "postgresql"],
            engineering_culture=culture,
            business_context="Leading fintech company",
            recent_news=["Acme raises Series D"],
            github_org_url="https://github.com/acme",
            public_repos_count=42,
            top_languages=["python", "go"],
            funding_stage="Series D",
        )
        assert profile.company_name == "Acme Corp"
        assert profile.industry == "fintech"
        assert profile.public_repos_count == 42
        assert len(profile.tech_stack_signals) == 3

    def test_company_profile_confidence_score_bounds_lower(self) -> None:
        """confidence_score of 0.0 should be accepted."""
        profile = self._make_profile(confidence_score=0.0)
        assert profile.confidence_score == 0.0

    def test_company_profile_confidence_score_bounds_upper(self) -> None:
        """confidence_score of 100.0 should be accepted."""
        profile = self._make_profile(confidence_score=100.0)
        assert profile.confidence_score == 100.0

    def test_company_profile_confidence_below_zero_rejected(self) -> None:
        """confidence_score below 0 should be rejected."""
        with pytest.raises(ValidationError):
            self._make_profile(confidence_score=-1.0)

    def test_company_profile_confidence_above_hundred_rejected(self) -> None:
        """confidence_score above 100 should be rejected."""
        with pytest.raises(ValidationError):
            self._make_profile(confidence_score=101.0)

    def test_company_profile_default_researched_at(self) -> None:
        """researched_at should default to approximately now UTC."""
        before = datetime.now(UTC)
        profile = self._make_profile()
        after = datetime.now(UTC)
        assert before <= profile.researched_at <= after


# ---------------------------------------------------------------------------
# intelligence_models.py — ResearchResult
# ---------------------------------------------------------------------------


class TestResearchResult:
    """Tests for ResearchResult model."""

    def test_research_result_full(self) -> None:
        """Full instantiation with metadata."""
        profile = CompanyProfile(
            company_name="Acme Corp",
            confidence_score=80.0,
        )
        result = ResearchResult(
            company_profile=profile,
            total_execution_time_seconds=15.3,
            agents_succeeded=5,
            agents_failed=1,
            partial=True,
        )
        assert result.company_profile.company_name == "Acme Corp"
        assert result.total_execution_time_seconds == 15.3
        assert result.agents_succeeded == 5
        assert result.agents_failed == 1
        assert result.partial is True

    def test_research_result_all_agents_succeeded(self) -> None:
        """Non-partial result when all agents succeed."""
        profile = CompanyProfile(
            company_name="BigCo",
            confidence_score=95.0,
        )
        result = ResearchResult(
            company_profile=profile,
            total_execution_time_seconds=8.0,
            agents_succeeded=6,
            agents_failed=0,
            partial=False,
        )
        assert result.partial is False
        assert result.agents_succeeded == 6
        assert result.agents_failed == 0
