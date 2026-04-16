"""Lirox v2.0 — Deep onboarding: niche-aware setup + learnings seeding."""
from lirox.onboarding.niche_profiles import (
    NICHE_QUESTIONS, get_niche_followups, all_niche_labels,
)
from lirox.onboarding.seed import seed_learnings_from_wizard

__all__ = [
    "NICHE_QUESTIONS", "get_niche_followups", "all_niche_labels",
    "seed_learnings_from_wizard",
]
