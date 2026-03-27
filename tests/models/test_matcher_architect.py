"""Comprehensive tests for matcher_models.py and architect_models.py."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from letsbuild.models.architect_models import (
    ADR,
    ADRStatus,
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.matcher_models import (
    DimensionScore,
    GapAnalysis,
    GapCategory,
    GapItem,
    MatchDimension,
    MatchScore,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gap_item(
    category: GapCategory = GapCategory.STRONG_MATCH,
    confidence: float = 85.0,
    suggested_project_demo: str | None = None,
) -> GapItem:
    return GapItem(
        skill_name="Python",
        category=category,
        confidence=confidence,
        evidence="5 years of production experience.",
        suggested_project_demo=suggested_project_demo,
    )


def _make_dimension_score(
    dimension: MatchDimension = MatchDimension.HARD_SKILLS,
    score: float = 90.0,
    weight: float = 0.30,
) -> DimensionScore:
    return DimensionScore(
        dimension=dimension,
        score=score,
        weight=weight,
        weighted_score=score * weight,
        details=f"Score for {dimension.value}.",
    )


def _make_all_dimension_scores() -> list[DimensionScore]:
    """Return dimension scores for all 6 dimensions summing weights to 1.0."""
    specs = [
        (MatchDimension.HARD_SKILLS, 85.0, 0.30),
        (MatchDimension.TECH_STACK, 80.0, 0.20),
        (MatchDimension.DOMAIN, 70.0, 0.15),
        (MatchDimension.PORTFOLIO, 75.0, 0.15),
        (MatchDimension.SENIORITY, 90.0, 0.10),
        (MatchDimension.SOFT_SKILLS, 60.0, 0.10),
    ]
    return [_make_dimension_score(d, s, w) for d, s, w in specs]


def _make_match_score() -> MatchScore:
    return MatchScore(
        overall_score=78.5,
        dimension_scores=_make_all_dimension_scores(),
        ats_predicted_score=82.0,
    )


def _make_sandbox_commands(n: int = 3) -> list[SandboxValidationCommand]:
    return [
        SandboxValidationCommand(
            command=f"echo test-{i}",
            description=f"Validation step {i}",
        )
        for i in range(n)
    ]


def _make_sandbox_plan() -> SandboxValidationPlan:
    return SandboxValidationPlan(commands=_make_sandbox_commands(3))


def _make_feature_spec(complexity: int = 5) -> FeatureSpec:
    return FeatureSpec(
        feature_name="auth",
        description="JWT authentication module.",
        module_path="src/auth.py",
        estimated_complexity=complexity,
    )


# ===================================================================
# matcher_models tests
# ===================================================================


class TestGapCategory:
    """GapCategory enum values."""

    @pytest.mark.parametrize(
        "member,value",
        [
            (GapCategory.STRONG_MATCH, "strong_match"),
            (GapCategory.DEMONSTRABLE_GAP, "demonstrable_gap"),
            (GapCategory.LEARNABLE_GAP, "learnable_gap"),
            (GapCategory.HARD_GAP, "hard_gap"),
            (GapCategory.PORTFOLIO_REDUNDANCY, "portfolio_redundancy"),
        ],
    )
    def test_gap_category_member_accessible(self, member: GapCategory, value: str) -> None:
        assert member.value == value

    def test_gap_category_has_exactly_five_members(self) -> None:
        assert len(GapCategory) == 5


class TestMatchDimension:
    """MatchDimension enum values."""

    @pytest.mark.parametrize(
        "member,value",
        [
            (MatchDimension.HARD_SKILLS, "hard_skills"),
            (MatchDimension.TECH_STACK, "tech_stack"),
            (MatchDimension.DOMAIN, "domain"),
            (MatchDimension.PORTFOLIO, "portfolio"),
            (MatchDimension.SENIORITY, "seniority"),
            (MatchDimension.SOFT_SKILLS, "soft_skills"),
        ],
    )
    def test_match_dimension_member_accessible(self, member: MatchDimension, value: str) -> None:
        assert member.value == value

    def test_match_dimension_has_exactly_six_members(self) -> None:
        assert len(MatchDimension) == 6


class TestGapItem:
    """GapItem model validation."""

    def test_valid_instantiation(self) -> None:
        item = _make_gap_item()
        assert item.skill_name == "Python"
        assert item.category == GapCategory.STRONG_MATCH
        assert item.confidence == 85.0
        assert item.suggested_project_demo is None

    def test_with_suggested_project_demo(self) -> None:
        item = _make_gap_item(suggested_project_demo="Build a REST API")
        assert item.suggested_project_demo == "Build a REST API"

    @pytest.mark.parametrize("category", list(GapCategory))
    def test_all_gap_categories_accepted(self, category: GapCategory) -> None:
        item = _make_gap_item(category=category)
        assert item.category == category

    def test_confidence_lower_bound(self) -> None:
        item = _make_gap_item(confidence=0.0)
        assert item.confidence == 0.0

    def test_confidence_upper_bound(self) -> None:
        item = _make_gap_item(confidence=100.0)
        assert item.confidence == 100.0

    def test_confidence_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_gap_item(confidence=-0.1)

    def test_confidence_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_gap_item(confidence=100.1)


class TestDimensionScore:
    """DimensionScore model validation."""

    def test_valid_instantiation(self) -> None:
        ds = _make_dimension_score()
        assert ds.dimension == MatchDimension.HARD_SKILLS
        assert ds.score == 90.0
        assert ds.weight == 0.30

    def test_weight_lower_bound(self) -> None:
        ds = _make_dimension_score(weight=0.0)
        assert ds.weight == 0.0

    def test_weight_upper_bound(self) -> None:
        ds = _make_dimension_score(weight=1.0)
        assert ds.weight == 1.0

    def test_weight_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_dimension_score(weight=-0.01)

    def test_weight_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_dimension_score(weight=1.01)

    def test_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_dimension_score(score=-1.0)

    def test_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_dimension_score(score=100.1)


class TestMatchScore:
    """MatchScore model and weight-sum validator."""

    def test_valid_instantiation(self) -> None:
        ms = _make_match_score()
        assert ms.overall_score == 78.5
        assert ms.ats_predicted_score == 82.0
        assert len(ms.dimension_scores) == 6

    def test_overall_score_bounds_zero(self) -> None:
        ms = MatchScore(
            overall_score=0.0,
            dimension_scores=_make_all_dimension_scores(),
            ats_predicted_score=0.0,
        )
        assert ms.overall_score == 0.0

    def test_overall_score_bounds_100(self) -> None:
        ms = MatchScore(
            overall_score=100.0,
            dimension_scores=_make_all_dimension_scores(),
            ats_predicted_score=100.0,
        )
        assert ms.overall_score == 100.0

    def test_overall_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MatchScore(
                overall_score=-1.0,
                dimension_scores=_make_all_dimension_scores(),
                ats_predicted_score=50.0,
            )

    def test_overall_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MatchScore(
                overall_score=100.1,
                dimension_scores=_make_all_dimension_scores(),
                ats_predicted_score=50.0,
            )

    def test_ats_predicted_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MatchScore(
                overall_score=50.0,
                dimension_scores=_make_all_dimension_scores(),
                ats_predicted_score=-0.1,
            )

    def test_ats_predicted_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MatchScore(
                overall_score=50.0,
                dimension_scores=_make_all_dimension_scores(),
                ats_predicted_score=100.1,
            )

    def test_dimension_weights_not_summing_to_one_rejected(self) -> None:
        bad_scores = [
            _make_dimension_score(MatchDimension.HARD_SKILLS, 80.0, 0.50),
            _make_dimension_score(MatchDimension.TECH_STACK, 80.0, 0.50),
            _make_dimension_score(MatchDimension.DOMAIN, 80.0, 0.50),
        ]
        with pytest.raises(ValidationError, match=r"weights must sum to 1\.0"):
            MatchScore(
                overall_score=80.0,
                dimension_scores=bad_scores,
                ats_predicted_score=80.0,
            )

    def test_empty_dimension_scores_skips_weight_validation(self) -> None:
        ms = MatchScore(
            overall_score=0.0,
            dimension_scores=[],
            ats_predicted_score=0.0,
        )
        assert ms.dimension_scores == []


class TestGapAnalysis:
    """GapAnalysis model validation."""

    def test_full_instantiation(self) -> None:
        ga = GapAnalysis(
            match_score=_make_match_score(),
            strong_matches=[_make_gap_item(GapCategory.STRONG_MATCH)],
            demonstrable_gaps=[_make_gap_item(GapCategory.DEMONSTRABLE_GAP)],
            learnable_gaps=[_make_gap_item(GapCategory.LEARNABLE_GAP)],
            hard_gaps=[_make_gap_item(GapCategory.HARD_GAP)],
            portfolio_redundancy=[_make_gap_item(GapCategory.PORTFOLIO_REDUNDANCY)],
            recommended_project_focus=["Python", "FastAPI", "Docker"],
            analysis_summary="Solid match with some learnable gaps.",
        )
        assert len(ga.strong_matches) == 1
        assert len(ga.demonstrable_gaps) == 1
        assert len(ga.learnable_gaps) == 1
        assert len(ga.hard_gaps) == 1
        assert len(ga.portfolio_redundancy) == 1
        assert ga.recommended_project_focus == ["Python", "FastAPI", "Docker"]
        assert isinstance(ga.analysed_at, datetime)

    def test_analysed_at_default_is_utc_now(self) -> None:
        before = datetime.now(UTC)
        ga = GapAnalysis(
            match_score=_make_match_score(),
            strong_matches=[],
            demonstrable_gaps=[],
            learnable_gaps=[],
            hard_gaps=[],
            portfolio_redundancy=[],
            recommended_project_focus=["skill1"],
            analysis_summary="Summary.",
        )
        after = datetime.now(UTC)
        assert before <= ga.analysed_at <= after

    def test_recommended_project_focus_min_one_required(self) -> None:
        with pytest.raises(ValidationError):
            GapAnalysis(
                match_score=_make_match_score(),
                strong_matches=[],
                demonstrable_gaps=[],
                learnable_gaps=[],
                hard_gaps=[],
                portfolio_redundancy=[],
                recommended_project_focus=[],
                analysis_summary="Summary.",
            )

    def test_recommended_project_focus_max_five(self) -> None:
        with pytest.raises(ValidationError):
            GapAnalysis(
                match_score=_make_match_score(),
                strong_matches=[],
                demonstrable_gaps=[],
                learnable_gaps=[],
                hard_gaps=[],
                portfolio_redundancy=[],
                recommended_project_focus=["a", "b", "c", "d", "e", "f"],
                analysis_summary="Summary.",
            )


# ===================================================================
# architect_models tests
# ===================================================================


class TestADRStatus:
    """ADRStatus enum values."""

    @pytest.mark.parametrize(
        "member,value",
        [
            (ADRStatus.PROPOSED, "proposed"),
            (ADRStatus.ACCEPTED, "accepted"),
            (ADRStatus.DEPRECATED, "deprecated"),
            (ADRStatus.SUPERSEDED, "superseded"),
        ],
    )
    def test_adr_status_member_accessible(self, member: ADRStatus, value: str) -> None:
        assert member.value == value

    def test_adr_status_has_exactly_four_members(self) -> None:
        assert len(ADRStatus) == 4


class TestADR:
    """ADR model validation."""

    def test_valid_instantiation(self) -> None:
        adr = ADR(
            title="Use FastAPI",
            status=ADRStatus.ACCEPTED,
            context="Need a performant async framework.",
            decision="Chose FastAPI for its OpenAPI support.",
            consequences="Tied to ASGI ecosystem.",
        )
        assert adr.title == "Use FastAPI"
        assert adr.status == ADRStatus.ACCEPTED
        assert adr.adr_id  # auto-generated UUID
        assert isinstance(adr.created_at, datetime)

    def test_default_timestamp_is_utc(self) -> None:
        before = datetime.now(UTC)
        adr = ADR(
            title="T",
            status=ADRStatus.PROPOSED,
            context="C",
            decision="D",
            consequences="Q",
        )
        after = datetime.now(UTC)
        assert before <= adr.created_at <= after

    def test_custom_adr_id_accepted(self) -> None:
        adr = ADR(
            adr_id="custom-id",
            title="T",
            status=ADRStatus.PROPOSED,
            context="C",
            decision="D",
            consequences="Q",
        )
        assert adr.adr_id == "custom-id"


class TestFileTreeNode:
    """FileTreeNode model including self-referential nesting."""

    def test_simple_file_node(self) -> None:
        node = FileTreeNode(path="src/main.py", is_directory=False)
        assert node.path == "src/main.py"
        assert node.is_directory is False
        assert node.children == []
        assert node.description is None

    def test_directory_node_with_children(self) -> None:
        child = FileTreeNode(path="src/utils.py", is_directory=False)
        parent = FileTreeNode(
            path="src/",
            is_directory=True,
            children=[child],
            description="Source code directory.",
        )
        assert parent.is_directory is True
        assert len(parent.children) == 1
        assert parent.children[0].path == "src/utils.py"

    def test_deeply_nested_tree(self) -> None:
        leaf = FileTreeNode(path="a/b/c/d.py", is_directory=False)
        c = FileTreeNode(path="a/b/c/", is_directory=True, children=[leaf])
        b = FileTreeNode(path="a/b/", is_directory=True, children=[c])
        a = FileTreeNode(path="a/", is_directory=True, children=[b])
        assert a.children[0].children[0].children[0].path == "a/b/c/d.py"


class TestSandboxValidationCommand:
    """SandboxValidationCommand defaults."""

    def test_default_exit_code_zero(self) -> None:
        cmd = SandboxValidationCommand(command="pytest tests/", description="Run tests.")
        assert cmd.expected_exit_code == 0

    def test_default_timeout_60(self) -> None:
        cmd = SandboxValidationCommand(command="pytest tests/", description="Run tests.")
        assert cmd.timeout_seconds == 60

    def test_custom_exit_code_and_timeout(self) -> None:
        cmd = SandboxValidationCommand(
            command="false",
            description="Expect failure.",
            expected_exit_code=1,
            timeout_seconds=120,
        )
        assert cmd.expected_exit_code == 1
        assert cmd.timeout_seconds == 120


class TestSandboxValidationPlan:
    """SandboxValidationPlan including min-3-commands constraint."""

    def test_valid_plan_with_three_commands(self) -> None:
        plan = _make_sandbox_plan()
        assert len(plan.commands) == 3
        assert plan.base_image == "letsbuild/sandbox:latest"
        assert plan.extra_packages == []
        assert plan.timeout_minutes == 20

    def test_fewer_than_three_commands_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SandboxValidationPlan(commands=_make_sandbox_commands(2))

    def test_custom_base_image_and_packages(self) -> None:
        plan = SandboxValidationPlan(
            commands=_make_sandbox_commands(3),
            base_image="custom:latest",
            extra_packages=["postgresql-client", "redis-tools"],
            timeout_minutes=30,
        )
        assert plan.base_image == "custom:latest"
        assert len(plan.extra_packages) == 2
        assert plan.timeout_minutes == 30


class TestFeatureSpec:
    """FeatureSpec model and complexity validation."""

    def test_valid_instantiation(self) -> None:
        fs = _make_feature_spec()
        assert fs.feature_name == "auth"
        assert fs.estimated_complexity == 5

    @pytest.mark.parametrize("complexity", [1, 5, 10])
    def test_complexity_valid_values(self, complexity: int) -> None:
        fs = _make_feature_spec(complexity=complexity)
        assert fs.estimated_complexity == complexity

    def test_complexity_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError, match="between 1 and 10"):
            _make_feature_spec(complexity=0)

    def test_complexity_above_ten_rejected(self) -> None:
        with pytest.raises(ValidationError, match="between 1 and 10"):
            _make_feature_spec(complexity=11)

    def test_default_dependencies_empty(self) -> None:
        fs = _make_feature_spec()
        assert fs.dependencies == []

    def test_default_acceptance_criteria_empty(self) -> None:
        fs = _make_feature_spec()
        assert fs.acceptance_criteria == []


class TestProjectSpec:
    """ProjectSpec model validation."""

    def _make_project_spec(self, **overrides: object) -> ProjectSpec:
        defaults: dict[str, object] = {
            "project_name": "smart-cache",
            "one_liner": "Distributed caching layer with eviction strategies.",
            "tech_stack": ["Python", "Redis"],
            "file_tree": [FileTreeNode(path="src/", is_directory=True)],
            "feature_specs": [_make_feature_spec()],
            "sandbox_validation_plan": _make_sandbox_plan(),
            "skill_name": "fullstack",
            "complexity_score": 6.5,
            "estimated_loc": 1500,
            "seniority_target": "mid",
        }
        defaults.update(overrides)
        return ProjectSpec(**defaults)  # type: ignore[arg-type]

    def test_full_instantiation(self) -> None:
        ps = self._make_project_spec()
        assert ps.project_name == "smart-cache"
        assert ps.complexity_score == 6.5
        assert len(ps.feature_specs) == 1

    def test_default_uuid_generated(self) -> None:
        ps = self._make_project_spec()
        assert ps.project_id  # non-empty string
        assert len(ps.project_id) == 36  # UUID4 format

    def test_default_designed_at_is_utc(self) -> None:
        before = datetime.now(UTC)
        ps = self._make_project_spec()
        after = datetime.now(UTC)
        assert before <= ps.designed_at <= after

    def test_complexity_score_lower_bound(self) -> None:
        ps = self._make_project_spec(complexity_score=1.0)
        assert ps.complexity_score == 1.0

    def test_complexity_score_upper_bound(self) -> None:
        ps = self._make_project_spec(complexity_score=10.0)
        assert ps.complexity_score == 10.0

    def test_complexity_score_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"between 1\.0 and 10\.0"):
            self._make_project_spec(complexity_score=0.9)

    def test_complexity_score_above_ten_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"between 1\.0 and 10\.0"):
            self._make_project_spec(complexity_score=10.1)

    def test_skill_coverage_map_default_empty(self) -> None:
        ps = self._make_project_spec()
        assert ps.skill_coverage_map == {}

    def test_skill_coverage_map_populated(self) -> None:
        ps = self._make_project_spec(
            skill_coverage_map={"Python": "Core language", "Redis": "Caching layer"}
        )
        assert len(ps.skill_coverage_map) == 2

    def test_adr_list_default_empty(self) -> None:
        ps = self._make_project_spec()
        assert ps.adr_list == []

    def test_json_schema_generation(self) -> None:
        schema = ProjectSpec.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "project_name" in schema["properties"]
        assert "complexity_score" in schema["properties"]
