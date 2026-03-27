"""Memory advisor for the Project Architect (Layer 4).

Queries the ReasoningBank (Layer 8) for similar past generations
to bias the architect toward proven designs and reduce retries.
This is the RETRIEVE step of the ReasoningBank learning pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import structlog

from letsbuild.models.intake_models import JDAnalysis  # noqa: TC001
from letsbuild.models.memory_models import DistilledPattern, ReasoningBankQuery

logger = structlog.get_logger(__name__)


@runtime_checkable
class MemoryStore(Protocol):
    """Protocol for the memory store backend (implemented in Steps 83-90)."""

    async def query_patterns(self, query: ReasoningBankQuery) -> list[DistilledPattern]: ...


@dataclass
class ArchitectAdvice:
    """Actionable advice for the Project Architect based on past patterns."""

    patterns: list[DistilledPattern] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    cold_start: bool = True


class MemoryAdvisor:
    """Queries ReasoningBank for similar past generations.

    During cold start (no memory store or no patterns), returns empty
    defaults so the pipeline proceeds without historical guidance.
    Once the ReasoningBank accumulates JUDGE verdicts and DISTILL
    patterns, the advisor biases the architect toward proven designs.
    """

    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        self._memory_store = memory_store
        self._log = logger.bind(component="memory_advisor")

    async def retrieve_patterns(
        self,
        jd_analysis: JDAnalysis,
        tech_stack: list[str] | None = None,
    ) -> list[DistilledPattern]:
        """Retrieve relevant patterns from the ReasoningBank.

        Args:
            jd_analysis: Parsed JD analysis from the Intake Engine.
            tech_stack: Optional explicit tech stack filter. If not provided,
                tech stack tags are derived from the JD analysis.

        Returns:
            List of distilled patterns relevant to this JD, or empty list
            on cold start.
        """
        query = self._build_query(jd_analysis, tech_stack)

        self._log.info(
            "retrieving_patterns",
            query_text=query.query_text,
            tech_stack_filter=query.tech_stack_filter,
            top_k=query.top_k,
            min_confidence=query.min_confidence,
        )

        if self._memory_store is None:
            self._log.info("cold_start_no_memory_store", patterns_returned=0)
            return []

        patterns = await self._memory_store.query_patterns(query)

        self._log.info(
            "patterns_retrieved",
            count=len(patterns),
            pattern_ids=[p.pattern_id for p in patterns],
        )

        return patterns

    async def get_recommendations(
        self,
        jd_analysis: JDAnalysis,
        tech_stack: list[str] | None = None,
    ) -> ArchitectAdvice:
        """Get actionable recommendations for the Project Architect.

        Retrieves patterns and formats them into human-readable suggestions
        with an overall confidence score.

        Args:
            jd_analysis: Parsed JD analysis from the Intake Engine.
            tech_stack: Optional explicit tech stack filter.

        Returns:
            ArchitectAdvice with patterns, suggestions, and confidence.
        """
        patterns = await self.retrieve_patterns(jd_analysis, tech_stack)

        if not patterns:
            self._log.info("cold_start_no_patterns")
            return ArchitectAdvice(
                patterns=[],
                suggestions=[],
                confidence=0.0,
                cold_start=True,
            )

        suggestions = self._format_suggestions(patterns)
        confidence = self._compute_confidence(patterns)

        self._log.info(
            "recommendations_ready",
            suggestion_count=len(suggestions),
            confidence=confidence,
        )

        return ArchitectAdvice(
            patterns=patterns,
            suggestions=suggestions,
            confidence=confidence,
            cold_start=False,
        )

    def _build_query(
        self,
        jd: JDAnalysis,
        tech_stack: list[str] | None,
    ) -> ReasoningBankQuery:
        """Construct a ReasoningBankQuery from JD analysis.

        Args:
            jd: Parsed JD analysis.
            tech_stack: Optional explicit tech stack filter.

        Returns:
            A ReasoningBankQuery ready for the memory store.
        """
        role_text = f"{jd.role_title} ({jd.role_category.value})"
        skill_names = [s.name for s in jd.required_skills]
        query_parts = [role_text, *skill_names]
        query_text = " | ".join(query_parts) if query_parts else role_text

        if tech_stack is not None:
            stack_filter = [t.lower() for t in tech_stack]
        else:
            stack_filter = [
                *jd.tech_stack.languages,
                *jd.tech_stack.frameworks,
                *jd.tech_stack.databases,
            ]

        return ReasoningBankQuery(
            query_text=query_text,
            tech_stack_filter=stack_filter,
            top_k=5,
            min_confidence=50.0,
        )

    @staticmethod
    def _format_suggestions(patterns: list[DistilledPattern]) -> list[str]:
        """Convert distilled patterns into human-readable suggestion strings."""
        suggestions: list[str] = []
        for pattern in patterns:
            tags = ", ".join(pattern.tech_stack_tags) if pattern.tech_stack_tags else "general"
            suggestion = (
                f"[{tags}] {pattern.pattern_text} "
                f"(confidence: {pattern.confidence:.0f}%, "
                f"success rate: {pattern.success_rate:.0f}%, "
                f"based on {pattern.sample_count} runs)"
            )
            suggestions.append(suggestion)
        return suggestions

    @staticmethod
    def _compute_confidence(patterns: list[DistilledPattern]) -> float:
        """Compute overall confidence from pattern confidences.

        Uses a weighted average where patterns with more samples
        contribute more to the overall confidence.
        """
        if not patterns:
            return 0.0

        total_weight = sum(p.sample_count for p in patterns)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(p.confidence * p.sample_count for p in patterns)
        return weighted_sum / total_weight
