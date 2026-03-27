"""Match & Score Engine (Layer 3) — 6-dimension weighted matching and gap analysis."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from letsbuild.matcher.ats_predictor import ATSPredictor
from letsbuild.matcher.gap_analysis import GapAnalyser
from letsbuild.models.intake_models import JDAnalysis  # noqa: TC001
from letsbuild.models.intelligence_models import CompanyProfile  # noqa: TC001
from letsbuild.models.matcher_models import (
    DimensionScore,
    GapAnalysis,
    GapCategory,
    GapItem,
    MatchDimension,
    MatchScore,
)

logger = structlog.get_logger()

# Canonical dimension weights — must sum to 1.0.
_DIMENSION_WEIGHTS: dict[MatchDimension, float] = {
    MatchDimension.HARD_SKILLS: 0.30,
    MatchDimension.TECH_STACK: 0.20,
    MatchDimension.DOMAIN: 0.15,
    MatchDimension.PORTFOLIO: 0.15,
    MatchDimension.SENIORITY: 0.10,
    MatchDimension.SOFT_SKILLS: 0.10,
}


class MatchEngine:
    """Performs 6-dimension weighted matching and gap categorisation.

    Pure Python / heuristic engine — no LLM calls. Accepts a user skill list
    and scores a JDAnalysis against it, producing a complete GapAnalysis.
    """

    def __init__(self, user_skills: list[str] | None = None) -> None:
        self._user_skills: list[str] = user_skills or []
        self._user_skills_set: set[str] = {s.lower().strip() for s in self._user_skills}
        self._gap_analyser = GapAnalyser()
        self._ats_predictor = ATSPredictor()
        self._log = logger.bind(component="match_engine")

    async def analyse(
        self,
        jd_analysis: JDAnalysis,
        company_profile: CompanyProfile | None = None,
    ) -> GapAnalysis:
        """Run the full match-and-score pipeline.

        Args:
            jd_analysis: Structured JD from Layer 1.
            company_profile: Optional company profile from Layer 2.

        Returns:
            Complete GapAnalysis with scores, gaps, and recommendations.
        """
        self._log.info(
            "match_analysis_started",
            role=jd_analysis.role_title,
            required_count=len(jd_analysis.required_skills),
            preferred_count=len(jd_analysis.preferred_skills),
            user_skills_count=len(self._user_skills),
        )

        match_score = self._score_dimensions(jd_analysis, company_profile)
        categorised = self._categorise_gaps(jd_analysis)
        focus = self._recommend_focus(categorised, jd_analysis)

        strong = categorised.get(GapCategory.STRONG_MATCH, [])
        demonstrable = categorised.get(GapCategory.DEMONSTRABLE_GAP, [])
        learnable = categorised.get(GapCategory.LEARNABLE_GAP, [])
        hard = categorised.get(GapCategory.HARD_GAP, [])
        redundancy = categorised.get(GapCategory.PORTFOLIO_REDUNDANCY, [])

        summary = self._build_summary(
            jd_analysis=jd_analysis,
            match_score=match_score,
            strong_count=len(strong),
            demonstrable_count=len(demonstrable),
            learnable_count=len(learnable),
            hard_count=len(hard),
        )

        analysis = GapAnalysis(
            match_score=match_score,
            strong_matches=strong,
            demonstrable_gaps=demonstrable,
            learnable_gaps=learnable,
            hard_gaps=hard,
            portfolio_redundancy=redundancy,
            recommended_project_focus=focus,
            analysis_summary=summary,
            analysed_at=datetime.now(UTC),
        )

        self._log.info(
            "match_analysis_complete",
            overall_score=match_score.overall_score,
            ats_score=match_score.ats_predicted_score,
            strong=len(strong),
            demonstrable=len(demonstrable),
            learnable=len(learnable),
            hard=len(hard),
        )

        return analysis

    # ------------------------------------------------------------------
    # Dimension scoring
    # ------------------------------------------------------------------

    def _score_dimensions(
        self,
        jd: JDAnalysis,
        company: CompanyProfile | None,
    ) -> MatchScore:
        """Compute 6-dimension weighted match score."""
        dimension_scores: list[DimensionScore] = []

        # 1. Hard Skills
        hard_score = self._score_hard_skills(jd)
        dimension_scores.append(hard_score)

        # 2. Tech Stack
        tech_score = self._score_tech_stack(jd, company)
        dimension_scores.append(tech_score)

        # 3. Domain
        domain_score = self._score_domain(jd, company)
        dimension_scores.append(domain_score)

        # 4. Portfolio (placeholder — full implementation needs PortfolioRegistry)
        portfolio_score = self._score_portfolio(jd)
        dimension_scores.append(portfolio_score)

        # 5. Seniority
        seniority_score = self._score_seniority(jd)
        dimension_scores.append(seniority_score)

        # 6. Soft Skills
        soft_score = self._score_soft_skills(jd)
        dimension_scores.append(soft_score)

        overall = round(sum(d.weighted_score for d in dimension_scores), 2)
        ats_score = self._ats_predictor.predict(jd, self._user_skills)

        return MatchScore(
            overall_score=overall,
            dimension_scores=dimension_scores,
            ats_predicted_score=ats_score,
        )

    def _score_hard_skills(self, jd: JDAnalysis) -> DimensionScore:
        """Score hard-skills dimension based on required skill overlap."""
        required_names = [s.name for s in jd.required_skills]
        overlap = self._gap_analyser.compute_skill_overlap(required_names, self._user_skills)
        weight = _DIMENSION_WEIGHTS[MatchDimension.HARD_SKILLS]
        return DimensionScore(
            dimension=MatchDimension.HARD_SKILLS,
            score=overlap,
            weight=weight,
            weighted_score=round(overlap * weight, 2),
            details=f"Matched {overlap:.0f}% of {len(required_names)} required skills.",
        )

    def _score_tech_stack(
        self,
        jd: JDAnalysis,
        company: CompanyProfile | None,
    ) -> DimensionScore:
        """Score tech-stack dimension using JD stack + optional company signals."""
        stack = jd.tech_stack
        all_tech: list[str] = (
            stack.languages
            + stack.frameworks
            + stack.databases
            + stack.cloud_providers
            + stack.tools
            + stack.infrastructure
        )

        # Augment with company tech stack signals if available
        if company and company.tech_stack_signals:
            extra = [
                s
                for s in company.tech_stack_signals
                if s.lower() not in {t.lower() for t in all_tech}
            ]
            all_tech = all_tech + extra

        overlap = self._gap_analyser.compute_skill_overlap(all_tech, self._user_skills)
        weight = _DIMENSION_WEIGHTS[MatchDimension.TECH_STACK]
        return DimensionScore(
            dimension=MatchDimension.TECH_STACK,
            score=overlap,
            weight=weight,
            weighted_score=round(overlap * weight, 2),
            details=f"Matched {overlap:.0f}% of {len(all_tech)} tech stack items.",
        )

    def _score_domain(
        self,
        jd: JDAnalysis,
        company: CompanyProfile | None,
    ) -> DimensionScore:
        """Score domain dimension based on domain keyword overlap."""
        domain_keywords = list(jd.domain_keywords)
        if (
            company
            and company.industry
            and company.industry.lower() not in {kw.lower() for kw in domain_keywords}
        ):
            domain_keywords.append(company.industry)

        overlap = self._gap_analyser.compute_skill_overlap(domain_keywords, self._user_skills)
        weight = _DIMENSION_WEIGHTS[MatchDimension.DOMAIN]
        return DimensionScore(
            dimension=MatchDimension.DOMAIN,
            score=overlap,
            weight=weight,
            weighted_score=round(overlap * weight, 2),
            details=f"Matched {overlap:.0f}% of {len(domain_keywords)} domain keywords.",
        )

    def _score_portfolio(self, jd: JDAnalysis) -> DimensionScore:
        """Score portfolio dimension.

        Placeholder: returns a neutral score. Full implementation will query
        the PortfolioRegistry (Layer 8) to check existing project coverage.
        """
        weight = _DIMENSION_WEIGHTS[MatchDimension.PORTFOLIO]
        score = 50.0  # Neutral until PortfolioRegistry is integrated
        return DimensionScore(
            dimension=MatchDimension.PORTFOLIO,
            score=score,
            weight=weight,
            weighted_score=round(score * weight, 2),
            details="Portfolio scoring pending — PortfolioRegistry integration required.",
        )

    def _score_seniority(self, jd: JDAnalysis) -> DimensionScore:
        """Score seniority dimension.

        Without full user profile, applies heuristic based on whether
        the JD specifies experience requirements.
        """
        weight = _DIMENSION_WEIGHTS[MatchDimension.SENIORITY]
        # Neutral default; user profile integration will refine this.
        score = 60.0
        detail = "Seniority scoring uses neutral baseline."
        if jd.years_experience_min is not None:
            detail = (
                f"JD requires {jd.years_experience_min}"
                f"{'-' + str(jd.years_experience_max) if jd.years_experience_max else '+'}"
                " years experience. User profile integration will refine."
            )
        return DimensionScore(
            dimension=MatchDimension.SENIORITY,
            score=score,
            weight=weight,
            weighted_score=round(score * weight, 2),
            details=detail,
        )

    def _score_soft_skills(self, jd: JDAnalysis) -> DimensionScore:
        """Score soft-skills dimension from key responsibilities text.

        Checks for common soft-skill keywords in responsibilities.
        """
        weight = _DIMENSION_WEIGHTS[MatchDimension.SOFT_SKILLS]
        soft_keywords = {
            "leadership",
            "mentoring",
            "communication",
            "collaboration",
            "teamwork",
            "problem-solving",
            "analytical",
            "stakeholder",
            "cross-functional",
            "presentation",
            "ownership",
            "initiative",
        }
        responsibilities_text = " ".join(jd.key_responsibilities).lower()
        found = {kw for kw in soft_keywords if kw in responsibilities_text}
        if not soft_keywords:
            score = 50.0
        else:
            # Give partial credit: matching soft skills is less binary
            score = min(100.0, (len(found) / max(len(soft_keywords), 1)) * 100.0 + 30.0)
        score = round(score, 2)
        return DimensionScore(
            dimension=MatchDimension.SOFT_SKILLS,
            score=score,
            weight=weight,
            weighted_score=round(score * weight, 2),
            details=f"Detected {len(found)} soft-skill keywords in responsibilities.",
        )

    # ------------------------------------------------------------------
    # Gap categorisation
    # ------------------------------------------------------------------

    def _categorise_gaps(self, jd: JDAnalysis) -> dict[str, list[GapItem]]:
        """Categorise every skill from the JD into gap buckets."""
        result: dict[str, list[GapItem]] = {
            GapCategory.STRONG_MATCH: [],
            GapCategory.DEMONSTRABLE_GAP: [],
            GapCategory.LEARNABLE_GAP: [],
            GapCategory.HARD_GAP: [],
            GapCategory.PORTFOLIO_REDUNDANCY: [],
        }

        all_skills: list[tuple[str, str, bool]] = []
        for skill in jd.required_skills:
            all_skills.append((skill.name, skill.category, True))
        for skill in jd.preferred_skills:
            all_skills.append((skill.name, skill.category, False))

        for skill_name, _skill_category, is_required in all_skills:
            category = self._gap_analyser.categorise_skill(
                skill_name,
                self._user_skills_set,
            )

            evidence = self._build_evidence(
                skill_name=skill_name,
                category=category,
                is_required=is_required,
            )

            suggested_demo: str | None = None
            if category in (GapCategory.DEMONSTRABLE_GAP, GapCategory.LEARNABLE_GAP):
                suggested_demo = (
                    f"Build a project feature using {skill_name} "
                    f"to demonstrate practical competency."
                )

            confidence = 90.0 if category == GapCategory.STRONG_MATCH else 75.0

            item = GapItem(
                skill_name=skill_name,
                category=category,
                confidence=confidence,
                evidence=evidence,
                suggested_project_demo=suggested_demo,
            )
            result[category].append(item)

        return result

    @staticmethod
    def _build_evidence(
        skill_name: str,
        category: GapCategory,
        is_required: bool,
    ) -> str:
        """Build a human-readable evidence string for a gap categorisation."""
        req_label = "required" if is_required else "preferred"
        if category == GapCategory.STRONG_MATCH:
            return f"User has direct experience with {skill_name} ({req_label} skill)."
        if category == GapCategory.DEMONSTRABLE_GAP:
            return (
                f"User has related skills that transfer to {skill_name} ({req_label} skill). "
                f"A targeted project can demonstrate competency."
            )
        if category == GapCategory.LEARNABLE_GAP:
            return f"{skill_name} is broadly learnable and can be acquired quickly ({req_label} skill)."
        return f"No existing skills closely relate to {skill_name} ({req_label} skill)."

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _recommend_focus(
        self,
        gaps: dict[str, list[GapItem]],
        jd: JDAnalysis,
    ) -> list[str]:
        """Pick top 3-5 skills to focus on in the generated project.

        Prioritises demonstrable gaps for required skills, then preferred.
        Falls back to learnable gaps and strong matches to fill the list.
        """
        required_names = {s.name.lower() for s in jd.required_skills}
        focus: list[str] = []

        # Priority 1: demonstrable gaps on required skills
        for item in gaps.get(GapCategory.DEMONSTRABLE_GAP, []):
            if item.skill_name.lower() in required_names and item.skill_name not in focus:
                focus.append(item.skill_name)
            if len(focus) >= 5:
                break

        # Priority 2: demonstrable gaps on preferred skills
        if len(focus) < 5:
            for item in gaps.get(GapCategory.DEMONSTRABLE_GAP, []):
                if item.skill_name not in focus:
                    focus.append(item.skill_name)
                if len(focus) >= 5:
                    break

        # Priority 3: learnable gaps (required first)
        if len(focus) < 3:
            for item in gaps.get(GapCategory.LEARNABLE_GAP, []):
                if item.skill_name.lower() in required_names and item.skill_name not in focus:
                    focus.append(item.skill_name)
                if len(focus) >= 5:
                    break

        if len(focus) < 3:
            for item in gaps.get(GapCategory.LEARNABLE_GAP, []):
                if item.skill_name not in focus:
                    focus.append(item.skill_name)
                if len(focus) >= 5:
                    break

        # Priority 4: strong matches to showcase
        if len(focus) < 3:
            for item in gaps.get(GapCategory.STRONG_MATCH, []):
                if item.skill_name.lower() in required_names and item.skill_name not in focus:
                    focus.append(item.skill_name)
                if len(focus) >= 5:
                    break

        # Ensure at least 1 item (model requires min_length=1)
        if not focus:
            if jd.required_skills:
                focus.append(jd.required_skills[0].name)
            elif jd.preferred_skills:
                focus.append(jd.preferred_skills[0].name)
            else:
                focus.append(jd.role_title)

        return focus[:5]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        jd_analysis: JDAnalysis,
        match_score: MatchScore,
        strong_count: int,
        demonstrable_count: int,
        learnable_count: int,
        hard_count: int,
    ) -> str:
        """Build a human-readable analysis summary."""
        total = strong_count + demonstrable_count + learnable_count + hard_count
        return (
            f"Match analysis for '{jd_analysis.role_title}': "
            f"overall score {match_score.overall_score:.1f}/100, "
            f"ATS predicted {match_score.ats_predicted_score:.1f}/100. "
            f"Of {total} skills evaluated: "
            f"{strong_count} strong matches, "
            f"{demonstrable_count} demonstrable gaps, "
            f"{learnable_count} learnable gaps, "
            f"{hard_count} hard gaps."
        )
