"""
Lirox v1.1 — Living Soul Engine

The soul is a dynamic document that evolves with the user.
It's not a fixed config — it grows, changes personality, learns quirks,
develops opinions about the user's work, and shapes how the Mind Agent responds.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from lirox.config import MIND_SOUL_FILE


DEFAULT_SOUL_STATE = {
    "version": "1.1",
    "created_at": None,
    "name": "Lirox",                    # Agent name (customizable)
    "personality": {
        "core": "direct, honest, insightful",
        "tone": "professional but human",
        "quirks": [],                    # Grows with interactions
        "values": [
            "Always give real recommendations, not hedged non-answers",
            "Be specific — vague advice is worthless",
            "Tell the user what they need to hear, not what they want to hear",
            "Show your reasoning, not just the conclusion",
        ],
    },
    "advisor_mode": {
        "style": "strategic advisor",
        "format": "recommendation + reasoning + next step",
        "depth": "medium",               # short / medium / deep
        "proactive": True,               # Suggest things unprompted
    },
    "growth_log": [],                    # Log of how the soul evolved
    "interaction_count": 0,
    "last_updated": None,
}


class LivingSoul:
    """
    The Mind Agent's living identity.
    Evolves based on interactions, user corrections, and /train results.
    """

    def __init__(self):
        self._path = Path(MIND_SOUL_FILE)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> Dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        state = dict(DEFAULT_SOUL_STATE)
        state["created_at"] = datetime.now().isoformat()
        return state

    def save(self) -> None:
        """Atomic save (FIX-07b)."""
        import os
        self.state["last_updated"] = datetime.now().isoformat()
        tmp_path = str(self._path) + ".tmp"
        try:
            with open(tmp_path, "w") as f:
                json.dump(self.state, f, indent=2, default=str)
            os.replace(tmp_path, str(self._path))
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    def get_name(self) -> str:
        return self.state.get("name", "Lirox")

    def set_name(self, name: str) -> None:
        self.state["name"] = name
        self._log_growth(f"Renamed to: {name}")
        self.save()

    def increment_interactions(self) -> None:
        """Increment interaction counter. Saves lazily every 10 interactions."""
        self.state["interaction_count"] = self.state.get("interaction_count", 0) + 1
        # BUG-3 FIX: only write to disk every 10 interactions, not every message
        if self.state["interaction_count"] % 10 == 0:
            self.save()

    def flush(self) -> None:
        """Force-save immediately (called on /train, /soul, shutdown)."""
        self.save()

    def add_quirk(self, quirk: str) -> None:
        """Add a personality quirk learned from the user."""
        quirks = self.state["personality"].get("quirks", [])
        if quirk not in quirks:
            quirks.append(quirk)
            if len(quirks) > 20:
                quirks = quirks[-20:]
            self.state["personality"]["quirks"] = quirks
            self._log_growth(f"Learned quirk: {quirk}")
            self.save()

    def update_advisor_depth(self, depth: str) -> None:
        """User prefers short/medium/deep responses."""
        if depth in ("short", "medium", "deep"):
            self.state["advisor_mode"]["depth"] = depth
            self._log_growth(f"Response depth set to: {depth}")
            self.save()

    def set_tone(self, tone: str) -> None:
        self.state["personality"]["tone"] = tone
        self._log_growth(f"Tone updated to: {tone}")
        self.save()

    def _log_growth(self, entry: str) -> None:
        self.state["growth_log"].append({
            "entry": entry,
            "at": datetime.now().isoformat(),
        })
        # Keep last 50 entries
        if len(self.state["growth_log"]) > 50:
            self.state["growth_log"] = self.state["growth_log"][-50:]

    def to_system_prompt(self, learnings_context: str = "") -> str:
        """Build the full system prompt for the Mind Agent."""
        p = self.state["personality"]
        am = self.state["advisor_mode"]
        name = self.get_name()
        depth_map = {
            "short": "Be concise. 3-5 sentences max per point.",
            "medium": "Give substance. Cover the key angles without padding.",
            "deep":   "Go deep. Full analysis with trade-offs, risks, and detailed recommendations.",
        }
        depth_instruction = depth_map.get(am.get("depth", "medium"), depth_map["medium"])

        quirks_text = ""
        if p.get("quirks"):
            quirks_text = "\nPERSONALITY QUIRKS (learned from this user):\n" + \
                          "\n".join(f"• {q}" for q in p["quirks"][-5:])

        values_text = "\n".join(f"• {v}" for v in p.get("values", []))

        learnings_section = ""
        if learnings_context.strip():
            learnings_section = (
                f"\n\n━━━ USER KNOWLEDGE BASE ━━━\n"
                f"(Extracted from conversations — USE THIS to personalize every response)\n\n"
                f"{learnings_context}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

        return f"""You are {name} — a personal AI advisor, not a generic assistant.

CORE IDENTITY
You are a {p.get("core", "direct, insightful")} advisor.
Tone: {p.get("tone", "professional but human")}.
Role: {am.get("style", "strategic advisor")} — you give recommendations and plans, not just information.

VALUES (non-negotiable):
{values_text}

RESPONSE FORMAT
{depth_instruction}
Default structure: Give your recommendation → explain reasoning → suggest the concrete next step.
When asked for a plan: numbered steps with expected outcomes.
When reviewing work: specific critique + specific improvements, not generic praise.
When the user is stuck: identify the root blocker, not surface symptoms.
{quirks_text}

ADVISOR RULES
• You know this user. Use that knowledge to personalize every response.
• You give opinions. When asked "what should I do?" — tell them what to do.
• You flag risks. If you see a problem the user hasn't mentioned, say it.
• You push back. If the user's plan has a flaw, point it out respectfully.
• You are NOT an answer machine. You are a thinking partner.
• Never pad responses with disclaimers, "Great question!", or "I hope this helps".
• If you don't know something, say "I don't know" — then suggest how to find out.
{learnings_section}"""

    def display_summary(self) -> str:
        """For /soul command."""
        p = self.state["personality"]
        am = self.state["advisor_mode"]
        lines = [
            f"  Name        : {self.get_name()}",
            f"  Core        : {p.get('core', '-')}",
            f"  Tone        : {p.get('tone', '-')}",
            f"  Style       : {am.get('style', '-')}",
            f"  Depth       : {am.get('depth', '-')}",
            f"  Interactions: {self.state.get('interaction_count', 0)}",
            f"  Quirks      : {len(p.get('quirks', []))} learned",
        ]
        if p.get("quirks"):
            for q in p["quirks"][-3:]:
                lines.append(f"              └ {q}")
        if self.state["growth_log"]:
            lines.append("\n  Recent growth:")
            for entry in self.state["growth_log"][-3:]:
                lines.append(f"    • {entry['entry']}")
        return "\n".join(lines)
