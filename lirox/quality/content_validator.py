"""
Content Validator
Detects repetition and context contamination in generated content.
"""
import logging
from typing import List

from lirox.quality.similarity import calculate_similarity

_logger = logging.getLogger("lirox.quality.validator")

# Similarity threshold above which content is considered repetitive
_REPETITION_THRESHOLD = 0.70

# Tech markers that shouldn't appear in non-tech documents.
# IMPORTANT: use FULL PHRASES — single words like 'library', 'code', 'framework'
# are perfectly valid in historical/religious contexts ("code of conduct",
# "library of scriptures", "philosophical framework") and must NOT be matched alone.
_TECH_MARKERS = frozenset([
    "software developer",
    "software engineer",
    "software library",
    "open source library",
    "npm package",
    "pip install",
    "import numpy",
    "import pandas",
    "github repository",
    "git commit",
    "pull request",
    "docker container",
    "kubernetes cluster",
    "machine learning model",
    "neural network",
    "programming language",
    "source code",
    "write code",
    "coding skills",
    "javascript framework",
    "react component",
    "rest api",
    "sql query",
    "database schema",
])

# Profile/personal markers that shouldn't appear in academic/historical docs
_PROFILE_MARKERS = frozenset([
    "as a developer", "as a software", "my experience at", "my github",
    "cv folder", "lirox", "gimp project", "my background in tech",
])


class ContentValidator:
    """Validates generated content for quality and domain relevance."""

    # ── Repetition detection ─────────────────────────────────────────────────

    def is_repetitive(self, new_content: str, previous_contents: List[str]) -> bool:
        """
        Return True if new_content is too similar to any previously generated section.

        Fixes the "same paragraph 20 times" bug by enforcing a Jaccard
        similarity ceiling across all prior sections.
        """
        for prev in previous_contents:
            sim = calculate_similarity(new_content, prev)
            if sim > _REPETITION_THRESHOLD:
                _logger.warning(
                    "Repetitive content detected — similarity %.2f (threshold %.2f)",
                    sim, _REPETITION_THRESHOLD,
                )
                return True
        return False

    # ── Relevance checks ─────────────────────────────────────────────────────

    def is_relevant(self, content: str, domain: str) -> bool:
        """
        Return True if content is relevant to the given domain.

        Two checks:
        1. At least 2 domain keywords present
        2. No inappropriate cross-domain contamination
        """
        content_lower = content.lower()
        domain_kws = self._domain_keywords(domain)

        hits = sum(1 for kw in domain_kws if kw in content_lower)
        if hits < 2:
            _logger.warning(
                "Content has only %d/%d domain keywords for '%s'",
                hits, len(domain_kws), domain,
            )
            # Lenient — don't hard-fail, just log; short sections may have few matches
            # Only fail for truly zero hits on large content blocks
            if hits == 0 and len(content) > 500:
                return False

        if self._is_contaminated(content_lower, domain):
            return False

        return True

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _domain_keywords(self, domain: str) -> List[str]:
        d = domain.lower()

        if any(w in d for w in ("sikh", "religion", "faith", "theology", "spiritual")):
            return ["sikh", "guru", "religion", "faith", "spiritual", "temple", "prayer",
                    "gurdwara", "granth", "singh", "kaur", "worship"]

        if any(w in d for w in ("fitness", "gym", "workout", "exercise")):
            return ["fitness", "gym", "workout", "exercise", "training", "health",
                    "muscle", "cardio", "strength", "coach"]

        if any(w in d for w in ("restaurant", "food", "dining", "culinary")):
            return ["food", "restaurant", "chef", "menu", "dining", "cuisine",
                    "cooking", "dish", "recipe", "flavour"]

        if any(w in d for w in ("software", "tech", "saas", "startup", "app")):
            return ["software", "technology", "code", "development", "product",
                    "platform", "users", "features", "data"]

        if any(w in d for w in ("history", "historical", "civilization", "ancient")):
            return ["history", "historical", "era", "century", "period",
                    "empire", "culture", "society", "tradition"]

        # Generic: use words from the domain itself
        return [w for w in d.split() if len(w) > 3]

    def _is_contaminated(self, content_lower: str, domain: str) -> bool:
        """Detect unambiguous cross-domain contamination using full-phrase matching."""
        d = domain.lower()
        is_tech = any(w in d for w in ("software", "tech", "saas", "app", "code", "developer"))
        is_historical = any(w in d for w in (
            "history", "sikh", "religion", "mythology", "biography",
            "ancient", "medieval", "civilization", "culture",
        ))

        if not is_tech:
            # Only match full unambiguous tech phrases — never single words
            if any(marker in content_lower for marker in _TECH_MARKERS):
                _logger.warning("Tech contamination in non-tech domain '%s'", domain)
                return True

        if is_historical:
            if any(marker in content_lower for marker in _PROFILE_MARKERS):
                _logger.warning("Profile contamination in historical/academic domain '%s'", domain)
                return True

        return False
