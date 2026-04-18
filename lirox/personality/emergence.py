"""Lirox V1 — Personality Emergence System.

Generates unique, context-aware personality traits from user profile data and
updates those traits over time as conversation patterns evolve.

The personality influences:
  - Response tone (formal/casual/witty/direct)
  - Vocabulary choices
  - Proactive suggestions
  - How the agent refers to itself and the user

Usage:
    from lirox.personality.emergence import PersonalityEngine

    engine = PersonalityEngine()
    traits = engine.generate_from_profile(profile_data, learnings_data)
    engine.persist(traits)
    style_hint = engine.get_style_hint()  # → "Be concise and technical."
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Storage ───────────────────────────────────────────────────────────────────

def _personality_file() -> Path:
    from lirox.config import MIND_DIR
    return Path(MIND_DIR) / "personality.json"


# ── Default traits ────────────────────────────────────────────────────────────

_DEFAULT_TRAITS: Dict[str, Any] = {
    "tone":             "direct",          # formal | casual | witty | direct
    "verbosity":        "concise",         # minimal | concise | detailed
    "proactivity":      "medium",          # low | medium | high
    "technical_depth":  "adaptive",        # basic | adaptive | deep
    "humor":            False,
    "use_emojis":       False,
    "signature_phrase": "",
    "core_values":      [],
    "communication_quirks": [],
    "updated_at":       "",
}


# ── Personality Engine ────────────────────────────────────────────────────────

class PersonalityEngine:
    """Generates and evolves agent personality traits from user profile + learnings."""

    def __init__(self) -> None:
        self._traits: Optional[Dict[str, Any]] = None

    # ── Public API ────────────────────────────────────────────────────────

    def load(self) -> Dict[str, Any]:
        """Load persisted personality traits (or return defaults)."""
        if self._traits is not None:
            return self._traits
        p = _personality_file()
        if p.exists():
            try:
                self._traits = json.loads(p.read_text(encoding="utf-8"))
                return self._traits
            except Exception:
                pass
        self._traits = dict(_DEFAULT_TRAITS)
        return self._traits

    def generate_from_profile(
        self,
        profile_data: Dict[str, Any],
        learnings_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Derive personality traits from the user's profile and learned facts.

        This is heuristic-based (no LLM call needed) so it works offline.
        """
        traits = dict(_DEFAULT_TRAITS)

        niche   = (profile_data.get("niche") or "").lower()
        goals   = profile_data.get("goals", []) or []
        prefs   = profile_data.get("preferences") or {}
        project = (profile_data.get("current_project") or "").lower()

        # Tone based on niche
        technical_niches = {"software", "dev", "engineering", "data", "research",
                             "security", "ml", "ai", "devops", "sre"}
        creative_niches  = {"design", "art", "music", "writing", "content",
                             "marketing", "brand"}
        business_niches  = {"startup", "business", "finance", "sales",
                             "consulting", "management"}

        for t in technical_niches:
            if t in niche:
                traits["tone"]           = "direct"
                traits["technical_depth"] = "deep"
                break
        for t in creative_niches:
            if t in niche:
                traits["tone"]          = "casual"
                traits["use_emojis"]    = True
                traits["humor"]         = True
                break
        for t in business_niches:
            if t in niche:
                traits["tone"]      = "formal"
                traits["verbosity"] = "detailed"
                break

        # Proactivity from goals
        if len(goals) >= 3:
            traits["proactivity"] = "high"
        elif len(goals) >= 1:
            traits["proactivity"] = "medium"

        # Core values from explicit goals
        traits["core_values"] = [g[:60] for g in goals[:3] if g]

        # Communication style from learnings
        if learnings_data:
            comm_style = learnings_data.get("communication_style") or {}
            if isinstance(comm_style, dict):
                for k, v in comm_style.items():
                    if "brief" in str(v).lower() or "short" in str(v).lower():
                        traits["verbosity"] = "minimal"
                    if "detailed" in str(v).lower() or "thorough" in str(v).lower():
                        traits["verbosity"] = "detailed"
                    if "casual" in str(v).lower() or "informal" in str(v).lower():
                        traits["tone"] = "casual"

        # Add quirk based on project
        if project:
            traits["communication_quirks"] = [
                f"Regularly references the active project: {project[:40]}"
            ]

        traits["updated_at"] = datetime.now().isoformat()
        self._traits = traits
        return traits

    def persist(self, traits: Optional[Dict[str, Any]] = None) -> None:
        """Save traits to disk."""
        t = traits or self._traits or dict(_DEFAULT_TRAITS)
        try:
            p = _personality_file()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def update_from_conversation(self, user_msg: str, agent_msg: str) -> None:
        """Incrementally update personality hints from a single exchange."""
        traits = self.load()
        text = (user_msg + " " + agent_msg).lower()

        # Detect preference signals
        if any(w in text for w in ("please be brief", "keep it short", "tldr")):
            traits["verbosity"] = "minimal"
        if any(w in text for w in ("in detail", "explain fully", "elaborate")):
            traits["verbosity"] = "detailed"
        if any(w in text for w in ("lol", "haha", "funny", "😂", "😄")):
            traits["humor"] = True

        traits["updated_at"] = datetime.now().isoformat()
        self._traits = traits
        self.persist(traits)

    def get_style_hint(self) -> str:
        """Return a system-prompt hint string derived from current personality."""
        t = self.load()
        parts: List[str] = []

        tone = t.get("tone", "direct")
        if tone == "formal":
            parts.append("Use a professional, formal tone.")
        elif tone == "casual":
            parts.append("Be warm, casual, and approachable.")
        elif tone == "witty":
            parts.append("Be clever and occasionally witty.")
        else:
            parts.append("Be direct and to the point.")

        verbosity = t.get("verbosity", "concise")
        if verbosity == "minimal":
            parts.append("Keep responses short and dense.")
        elif verbosity == "detailed":
            parts.append("Give thorough, detailed responses.")
        else:
            parts.append("Be concise but complete.")

        if t.get("technical_depth") == "deep":
            parts.append("Use technical vocabulary appropriate to the domain.")

        if t.get("humor"):
            parts.append("Light humor is welcome where appropriate.")

        if not t.get("use_emojis", False):
            parts.append("Avoid decorative emojis in responses.")

        values = t.get("core_values", [])
        if values:
            parts.append(f"The user cares deeply about: {', '.join(values[:2])}.")

        return " ".join(parts)

    def summary(self) -> str:
        """Return a readable summary of current personality traits."""
        t = self.load()
        lines = [
            f"  Tone          : {t.get('tone', '–')}",
            f"  Verbosity     : {t.get('verbosity', '–')}",
            f"  Technical     : {t.get('technical_depth', '–')}",
            f"  Proactivity   : {t.get('proactivity', '–')}",
            f"  Humor         : {'yes' if t.get('humor') else 'no'}",
            f"  Emojis        : {'yes' if t.get('use_emojis') else 'no'}",
            f"  Core values   : {', '.join(t.get('core_values', [])) or '–'}",
            f"  Last updated  : {t.get('updated_at', '–')[:19]}",
        ]
        return "\n".join(lines)
