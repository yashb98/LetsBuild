"""ATS (Applicant Tracking System) score predictor — pure heuristic, no LLM calls."""

from __future__ import annotations

import structlog

from letsbuild.models.intake_models import JDAnalysis  # noqa: TC001

logger = structlog.get_logger()


class ATSPredictor:
    """Predicts an ATS match score using keyword-overlap heuristics.

    Weighting:
        - Required skills keyword overlap: 50%
        - Tech stack match: 25%
        - Years experience match: 15%
        - Domain relevance: 10%
    """

    def __init__(self) -> None:
        self._log = logger.bind(component="ats_predictor")

    def predict(self, jd_analysis: JDAnalysis, user_skills: list[str]) -> float:
        """Predict ATS match score for a user against a JD.

        Args:
            jd_analysis: Parsed job description.
            user_skills: User's skill names.

        Returns:
            Predicted ATS score from 0.0 to 100.0.
        """
        user_lower = {s.lower().strip() for s in user_skills}

        keyword_score = self._keyword_overlap_score(jd_analysis, user_lower)
        tech_score = self._tech_stack_score(jd_analysis, user_lower)
        experience_score = self._experience_score(jd_analysis)
        domain_score = self._domain_score(jd_analysis, user_lower)

        weighted = (
            keyword_score * 0.50 + tech_score * 0.25 + experience_score * 0.15 + domain_score * 0.10
        )

        final = round(min(max(weighted, 0.0), 100.0), 2)

        self._log.debug(
            "ats_prediction",
            keyword=keyword_score,
            tech=tech_score,
            experience=experience_score,
            domain=domain_score,
            final=final,
        )

        return final

    def _keyword_overlap_score(
        self,
        jd: JDAnalysis,
        user_lower: set[str],
    ) -> float:
        """Score based on required + preferred skills keyword match."""
        required_names = [s.name.lower().strip() for s in jd.required_skills]
        preferred_names = [s.name.lower().strip() for s in jd.preferred_skills]

        if not required_names and not preferred_names:
            return 50.0  # No skills listed — neutral score

        required_matched = sum(1 for s in required_names if self._fuzzy_in(s, user_lower))
        preferred_matched = sum(1 for s in preferred_names if self._fuzzy_in(s, user_lower))

        # Required skills matter more: 70% required, 30% preferred
        req_score = (required_matched / len(required_names) * 100.0) if required_names else 50.0
        pref_score = (preferred_matched / len(preferred_names) * 100.0) if preferred_names else 50.0

        return req_score * 0.70 + pref_score * 0.30

    def _tech_stack_score(self, jd: JDAnalysis, user_lower: set[str]) -> float:
        """Score based on tech stack alignment."""
        stack = jd.tech_stack
        all_tech: list[str] = (
            stack.languages
            + stack.frameworks
            + stack.databases
            + stack.cloud_providers
            + stack.tools
            + stack.infrastructure
        )
        if not all_tech:
            return 50.0

        matched = sum(1 for t in all_tech if self._fuzzy_in(t.lower(), user_lower))
        return round((matched / len(all_tech)) * 100.0, 2)

    def _experience_score(self, jd: JDAnalysis) -> float:
        """Score based on years of experience alignment.

        Without knowing the user's actual years, we return a neutral 60.0.
        This component can be enhanced when UserProfile is available.
        """
        # Placeholder: if JD specifies experience, give neutral score.
        # A future enhancement would accept user_years_experience.
        if jd.years_experience_min is not None:
            return 60.0
        return 70.0  # No requirement listed → slightly positive

    def _domain_score(self, jd: JDAnalysis, user_lower: set[str]) -> float:
        """Score based on domain keyword overlap."""
        if not jd.domain_keywords:
            return 50.0

        domain_lower = [kw.lower().strip() for kw in jd.domain_keywords]
        matched = sum(1 for kw in domain_lower if self._fuzzy_in(kw, user_lower))
        return round((matched / len(domain_lower)) * 100.0, 2)

    @staticmethod
    def _fuzzy_in(needle: str, haystack: set[str]) -> bool:
        """Check if needle matches any item in haystack (exact or substring)."""
        if needle in haystack:
            return True
        return any(needle in item or item in needle for item in haystack)
