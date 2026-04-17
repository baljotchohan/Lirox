"""Seed LearningsStore with data captured during the setup wizard.

The wizard collects niche, follow-ups, and goals. This module turns
that into first-class learnings so:
  • /recall immediately shows what the user told the wizard.
  • The agent's first reply is already personalized.
  • Downstream prompts (soul.to_system_prompt) include this data.
"""
from __future__ import annotations

from typing import Dict, Any, List


def seed_learnings_from_wizard(profile_data: Dict[str, Any],
                                niche_details: Dict[str, str],
                                goals: List[str]) -> Dict[str, int]:
    """Write wizard data into LearningsStore as facts/projects/topics.

    Returns stats: {"facts": N, "projects": N, "topics": N}.
    """
    from lirox.mind.agent import get_learnings
    learnings = get_learnings()

    stats = {"facts": 0, "projects": 0, "topics": 0}

    user_name = profile_data.get("user_name", "").strip()
    agent_name = profile_data.get("agent_name", "").strip()
    niche      = profile_data.get("niche", "").strip()
    project    = profile_data.get("current_project", "").strip()

    # Core identity facts
    if user_name:
        learnings.add_fact(f"User's name is {user_name}.", confidence=1.0, source="wizard")
        stats["facts"] += 1
    if agent_name:
        learnings.add_fact(f"Agent is named {agent_name}.", confidence=1.0, source="wizard")
        stats["facts"] += 1
    if niche:
        learnings.add_fact(f"User's primary work: {niche}.", confidence=1.0, source="wizard")
        stats["facts"] += 1

    # Niche follow-up details → facts + topics
    for key, val in (niche_details or {}).items():
        val = (val or "").strip()
        if not val:
            continue
        # Pretty-label the key (snake → Title)
        label = key.replace("_", " ").title()
        learnings.add_fact(f"{label}: {val}", confidence=0.95, source="wizard")
        stats["facts"] += 1
        # Promote short tokens as topics
        for tok in val.lower().replace(",", " ").split():
            if len(tok) > 3 and tok.isalnum():
                learnings.bump_topic(tok)
                stats["topics"] += 1

    # Current project → add as project record
    if project:
        learnings.add_project(project, description="")
        stats["projects"] += 1

    # Goals → facts
    for g in (goals or []):
        g = (g or "").strip()
        if g:
            learnings.add_fact(f"Goal: {g}", confidence=0.9, source="wizard")
            stats["facts"] += 1

    learnings.flush()
    return stats
