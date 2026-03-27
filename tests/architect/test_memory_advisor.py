"""Tests for the MemoryAdvisor — ReasoningBank query interface for Layer 4."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from letsbuild.architect.memory_advisor import ArchitectAdvice, MemoryAdvisor
from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.memory_models import DistilledPattern, ReasoningBankQuery


@pytest.fixture()
def sample_jd() -> JDAnalysis:
    """A minimal JDAnalysis for testing."""
    return JDAnalysis(
        role_title="Senior Backend Engineer",
        role_category=RoleCategory.BACKEND,
        seniority=SeniorityLevel.SENIOR,
        required_skills=[
            Skill(name="Python", category="language", is_primary=True),
            Skill(name="FastAPI", category="framework", is_primary=True),
        ],
        tech_stack=TechStack(
            languages=["python"],
            frameworks=["fastapi"],
            databases=["postgresql"],
        ),
        raw_text="We are looking for a Senior Backend Engineer...",
    )


@pytest.fixture()
def sample_patterns() -> list[DistilledPattern]:
    """A set of distilled patterns for testing."""
    return [
        DistilledPattern(
            pattern_id="pat-1",
            pattern_text="Use repository pattern for database access",
            source_verdicts=["v1", "v2"],
            confidence=85.0,
            tech_stack_tags=["python", "fastapi"],
            success_rate=90.0,
            sample_count=10,
            distilled_at=datetime(2026, 3, 1, tzinfo=UTC),
        ),
        DistilledPattern(
            pattern_id="pat-2",
            pattern_text="Add health check endpoint at /healthz",
            source_verdicts=["v3"],
            confidence=70.0,
            tech_stack_tags=["fastapi"],
            success_rate=95.0,
            sample_count=5,
            distilled_at=datetime(2026, 3, 15, tzinfo=UTC),
        ),
    ]


class MockMemoryStore:
    """A mock MemoryStore that returns pre-configured patterns."""

    def __init__(self, patterns: list[DistilledPattern]) -> None:
        self._patterns = patterns
        self.last_query: ReasoningBankQuery | None = None

    async def query_patterns(self, query: ReasoningBankQuery) -> list[DistilledPattern]:
        self.last_query = query
        return self._patterns


@pytest.mark.asyncio()
async def test_retrieve_patterns_cold_start_returns_empty(sample_jd: JDAnalysis) -> None:
    """Cold start (no memory store) returns an empty pattern list."""
    advisor = MemoryAdvisor(memory_store=None)
    patterns = await advisor.retrieve_patterns(sample_jd)
    assert patterns == []


@pytest.mark.asyncio()
async def test_get_recommendations_cold_start(sample_jd: JDAnalysis) -> None:
    """Cold start recommendations have empty suggestions and zero confidence."""
    advisor = MemoryAdvisor(memory_store=None)
    advice = await advisor.get_recommendations(sample_jd)

    assert isinstance(advice, ArchitectAdvice)
    assert advice.patterns == []
    assert advice.suggestions == []
    assert advice.confidence == 0.0


@pytest.mark.asyncio()
async def test_get_recommendations_cold_start_has_flag(sample_jd: JDAnalysis) -> None:
    """Cold start advice has cold_start=True."""
    advisor = MemoryAdvisor(memory_store=None)
    advice = await advisor.get_recommendations(sample_jd)

    assert advice.cold_start is True


@pytest.mark.asyncio()
async def test_build_query_from_jd(sample_jd: JDAnalysis) -> None:
    """_build_query constructs a correct ReasoningBankQuery from JD analysis."""
    advisor = MemoryAdvisor(memory_store=None)
    query = advisor._build_query(sample_jd, tech_stack=None)

    assert isinstance(query, ReasoningBankQuery)
    assert "Senior Backend Engineer" in query.query_text
    assert "backend_engineer" in query.query_text
    assert "Python" in query.query_text
    assert "FastAPI" in query.query_text
    assert "python" in query.tech_stack_filter
    assert "fastapi" in query.tech_stack_filter
    assert "postgresql" in query.tech_stack_filter
    assert query.top_k == 5
    assert query.min_confidence == 50.0


@pytest.mark.asyncio()
async def test_build_query_with_explicit_tech_stack(sample_jd: JDAnalysis) -> None:
    """_build_query uses explicit tech_stack when provided."""
    advisor = MemoryAdvisor(memory_store=None)
    query = advisor._build_query(sample_jd, tech_stack=["React", "TypeScript"])

    assert query.tech_stack_filter == ["react", "typescript"]


@pytest.mark.asyncio()
async def test_retrieve_with_mock_store(
    sample_jd: JDAnalysis,
    sample_patterns: list[DistilledPattern],
) -> None:
    """When a memory store is available, patterns are returned from it."""
    store = MockMemoryStore(sample_patterns)
    advisor = MemoryAdvisor(memory_store=store)

    patterns = await advisor.retrieve_patterns(sample_jd)

    assert len(patterns) == 2
    assert patterns[0].pattern_id == "pat-1"
    assert patterns[1].pattern_id == "pat-2"
    assert store.last_query is not None
    assert "Senior Backend Engineer" in store.last_query.query_text


@pytest.mark.asyncio()
async def test_recommendations_with_patterns(
    sample_jd: JDAnalysis,
    sample_patterns: list[DistilledPattern],
) -> None:
    """With patterns available, recommendations include suggestions and confidence."""
    store = MockMemoryStore(sample_patterns)
    advisor = MemoryAdvisor(memory_store=store)

    advice = await advisor.get_recommendations(sample_jd)

    assert advice.cold_start is False
    assert len(advice.patterns) == 2
    assert len(advice.suggestions) == 2
    assert advice.confidence > 0.0

    # Verify suggestions contain pattern text
    assert "repository pattern" in advice.suggestions[0]
    assert "health check" in advice.suggestions[1]

    # Confidence is weighted average: (85*10 + 70*5) / (10+5) = 80.0
    assert advice.confidence == pytest.approx(80.0)
