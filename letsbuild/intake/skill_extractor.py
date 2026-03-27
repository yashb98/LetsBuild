"""Rule-based skill extraction from job description text.

Uses the taxonomy JSON to match skills by canonical name and aliases,
producing n-grams (unigrams, bigrams, trigrams) for multi-word matches.
First stage of the 3-stage skill extraction pipeline
(rule-based -> spaCy NER -> LLM refinement).
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

# Confidence score for a single rule-based match.
_BASE_CONFIDENCE: float = 80.0

# Bonus confidence per additional mention (capped so total <= 100).
_REPEAT_BONUS: float = 5.0

# Maximum confidence score.
_MAX_CONFIDENCE: float = 100.0


class SkillExtractor:
    """Rule-based skill extractor that matches text tokens against a taxonomy.

    The taxonomy JSON has structure::

        {
          "version": "1.0",
          "categories": {
            "<category>": {
              "<canonical_name>": {
                "aliases": ["alias1", "alias2"],
                "category": "<category>"
              }
            }
          }
        }

    Each canonical name and its aliases are lowercased and stored in a flat
    lookup dict for O(1) matching.
    """

    def __init__(self, taxonomy_path: str | None = None) -> None:
        resolved_path = taxonomy_path or _DEFAULT_TAXONOMY_PATH
        taxonomy = self._load_taxonomy(resolved_path)
        self._lookup: dict[str, tuple[str, str]] = self._build_lookup(taxonomy)
        logger.info(
            "skill_extractor.initialised",
            taxonomy_path=resolved_path,
            lookup_entries=len(self._lookup),
        )

    @staticmethod
    def _load_taxonomy(path: str) -> dict[str, object]:
        """Load and return the taxonomy JSON.  Returns empty dict on error."""
        try:
            with open(path, encoding="utf-8") as fh:
                data: dict[str, object] = json.load(fh)
            return data
        except FileNotFoundError:
            logger.warning("skill_extractor.taxonomy_not_found", path=path)
            return {}
        except json.JSONDecodeError as exc:
            logger.warning(
                "skill_extractor.taxonomy_parse_error",
                path=path,
                error=str(exc),
            )
            return {}

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
        5.0 for each additional mention, capped at 100.0.
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
            confidence = min(
                _BASE_CONFIDENCE + _REPEAT_BONUS * (count - 1),
                _MAX_CONFIDENCE,
            )
            skills.append(
                Skill(
                    name=canonical,
                    category=category,
                    confidence=confidence,
                )
            )

        # Sort by confidence descending, then alphabetically for stability
        skills.sort(key=lambda s: (-s.confidence, s.name))
        logger.debug(
            "skill_extractor.extract",
            input_length=len(text),
            token_count=len(tokens),
            skills_found=len(skills),
        )
        return skills

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase *text* and produce unigrams, bigrams, and trigrams.

        Splits on whitespace and common delimiters (commas, semicolons,
        pipes, parentheses, brackets, newlines).  Preserves meaningful
        punctuation within tokens (e.g. ``c++``, ``c#``, ``node.js``,
        ``.net``, ``ci/cd``).
        """
        lowered = text.lower()
        # Replace delimiters with spaces, but keep hyphens, dots, slashes,
        # +, and # within tokens (for C#, F#, C++, .NET, CI/CD, etc.).
        cleaned = re.sub(r"[,;|()[\]{}\n\r\t]+", " ", lowered)
        words = cleaned.split()

        # Strip trailing punctuation that is not meaningful.
        stripped: list[str] = []
        for w in words:
            w = w.strip(":")
            # Remove trailing period unless it looks like part of a name
            # (e.g. "vue.js", "node.js").
            if w.endswith(".") and not re.search(r"\.\w", w):
                w = w.rstrip(".")
            if w:
                stripped.append(w)

        # Build n-grams.
        ngrams: list[str] = []
        for i, word in enumerate(stripped):
            # Unigram
            ngrams.append(word)
            # Bigram
            if i + 1 < len(stripped):
                ngrams.append(f"{word} {stripped[i + 1]}")
            # Trigram
            if i + 2 < len(stripped):
                ngrams.append(f"{word} {stripped[i + 1]} {stripped[i + 2]}")

        return ngrams
