"""Rule-based skill extraction from job description text.

Uses the taxonomy JSON to match skills by canonical name and aliases,
producing n-grams (unigrams, bigrams, trigrams) for multi-word matches.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from letsbuild.models.intake_models import Skill

logger = structlog.get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_TAXONOMY_PATH = str(_PROJECT_ROOT / "skills" / "taxonomy.json")


class SkillExtractor:
    """Rule-based skill extractor that matches text tokens against a taxonomy."""

    def __init__(self, taxonomy_path: str | None = None) -> None:
        resolved_path = taxonomy_path or _DEFAULT_TAXONOMY_PATH
        logger.info("loading_taxonomy", path=resolved_path)

        with open(resolved_path) as f:
            taxonomy: dict[str, object] = json.load(f)

        self._lookup: dict[str, tuple[str, str]] = self._build_lookup(taxonomy)
        logger.info("taxonomy_loaded", skill_count=len(self._lookup))

    @staticmethod
    def _build_lookup(taxonomy: dict[str, object]) -> dict[str, tuple[str, str]]:
        """Flatten taxonomy into {lowercase_name_or_alias: (canonical_name, category)}."""
        lookup: dict[str, tuple[str, str]] = {}
        categories = taxonomy.get("categories", {})
        if not isinstance(categories, dict):
            return lookup

        for _cat_key, skills in categories.items():
            if not isinstance(skills, dict):
                continue
            for canonical_name, details in skills.items():
                if not isinstance(details, dict):
                    continue
                category: str = details.get("category", _cat_key)
                # Map the canonical name itself
                lookup[canonical_name.lower()] = (canonical_name, category)
                # Map every alias
                for alias in details.get("aliases", []):
                    if isinstance(alias, str) and alias:
                        lookup[alias.lower()] = (canonical_name, category)

        return lookup

    def extract(self, text: str) -> list[Skill]:
        """Extract skills from *text* using n-gram matching against the taxonomy.

        Returns a de-duplicated list of :class:`Skill` objects sorted by
        confidence descending.  Confidence starts at 80.0 and increases by
        10.0 for each additional mention, capped at 100.0.
        """
        tokens = self._tokenize(text)
        # Count mentions per canonical name
        mention_counts: dict[str, tuple[str, int]] = {}  # canonical -> (category, count)

        for token in tokens:
            match = self._lookup.get(token)
            if match is None:
                continue
            canonical, category = match
            if canonical in mention_counts:
                existing_cat, count = mention_counts[canonical]
                mention_counts[canonical] = (existing_cat, count + 1)
            else:
                mention_counts[canonical] = (category, 1)

        skills: list[Skill] = []
        for canonical, (category, count) in mention_counts.items():
            confidence = min(80.0 + (count - 1) * 10.0, 100.0)
            skills.append(
                Skill(
                    name=canonical,
                    category=category,
                    confidence=confidence,
                )
            )

        # Sort by confidence descending, then alphabetically for stability
        skills.sort(key=lambda s: (-s.confidence, s.name))
        logger.debug("skills_extracted", count=len(skills))
        return skills

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase *text* and produce unigrams, bigrams, and trigrams."""
        # Split on whitespace and common punctuation, keeping meaningful tokens
        words = re.split(r"[,;|/\n\r\t]+|\s+", text.lower())
        words = [w.strip() for w in words if w.strip()]

        ngrams: list[str] = []
        for i, word in enumerate(words):
            # Unigram
            ngrams.append(word)
            # Bigram
            if i + 1 < len(words):
                ngrams.append(f"{word} {words[i + 1]}")
            # Trigram
            if i + 2 < len(words):
                ngrams.append(f"{word} {words[i + 1]} {words[i + 2]}")

        return ngrams
