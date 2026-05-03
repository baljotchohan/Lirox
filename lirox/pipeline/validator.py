"""
Content Validator (Pipeline Module)
Detects repetition and context contamination in generated content.
"""
import logging
from typing import List

from lirox.pipeline.similarity import calculate_similarity

_logger = logging.getLogger("lirox.pipeline.validator")

# Similarity threshold above which content is considered repetitive
_REPETITION_THRESHOLD = 0.70

# Tech markers that shouldn't appear in non-tech documents.
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

    def is_repetitive(self, new_content: str, previous_contents: List[str]) -> bool:
        """Return True if new_content is too similar to any previously generated section."""
        for prev in previous_contents:
            sim = calculate_similarity(new_content, prev)
            if sim > _REPETITION_THRESHOLD:
                _logger.warning(
                    "Repetitive content detected — similarity %.2f (threshold %.2f)",
                    sim, _REPETITION_THRESHOLD,
                )
                return True
        return False

    def is_relevant(self, content: str, domain: str) -> bool:
        """Return True if content is relevant to the given domain."""
        content_lower = content.lower()
        domain_kws = self._domain_keywords(domain)

        hits = sum(1 for kw in domain_kws if kw in content_lower)
        if hits < 2:
            _logger.warning(
                "Content has only %d/%d domain keywords for '%s'",
                hits, len(domain_kws), domain,
            )
            if hits == 0 and len(content) > 500:
                return False

        if self._is_contaminated(content_lower, domain):
            return False

        return True

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
        return [w for w in d.split() if len(w) > 3]

    def _is_contaminated(self, content_lower: str, domain: str) -> bool:
        """Detect unambiguous cross-domain contamination."""
        d = domain.lower()
        is_tech = any(w in d for w in ("software", "tech", "saas", "app", "code", "developer"))
        is_historical = any(w in d for w in (
            "history", "sikh", "religion", "mythology", "biography",
            "ancient", "medieval", "civilization", "culture",
        ))
        if not is_tech:
            if any(marker in content_lower for marker in _TECH_MARKERS):
                _logger.warning("Tech contamination in non-tech domain '%s'", domain)
                return True
        if is_historical:
            if any(marker in content_lower for marker in _PROFILE_MARKERS):
                _logger.warning("Profile contamination in historical/academic domain '%s'", domain)
                return True
        return False
