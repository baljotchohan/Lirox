"""
Lirox v0.5 — Training Engine

/train command implementation.
Analyzes current session memory + conversation history,
extracts structured learnings, saves them permanently.
"""
from __future__ import annotations

import json
import re
from typing import List, Dict, Any, Tuple

from lirox.mind.learnings import LearningsStore
from lirox.utils.llm import generate_response


# ── Extraction prompts ────────────────────────────────────────────────────────

_FACT_EXTRACT_PROMPT = """
You are a knowledge extractor for a personal AI agent.
Analyze this conversation and extract stable FACTS about the user.

Facts are things that will likely remain true tomorrow:
- Profession, job role, company
- Skills they have
- Projects they are working on
- Tools/languages they use
- Their location, timezone, working hours
- Goals they mentioned
- Personal preferences (tone, format, speed vs depth, etc.)

CONVERSATION:
{conversation}

Output ONLY a JSON array of fact strings (no markdown, no explanation):
["fact 1", "fact 2", ...]

If nothing worth learning, output: []
"""

_TOPIC_EXTRACT_PROMPT = """
Analyze this conversation and extract the main TOPICS discussed.
Be specific: "Python async programming" not just "programming".

CONVERSATION:
{conversation}

Output ONLY a JSON array of topic strings (max 10):
["topic 1", "topic 2", ...]
"""

_PREFERENCE_EXTRACT_PROMPT = """
Analyze this conversation for USER PREFERENCES and DISLIKES.
Look for:
- How they want responses formatted (short/long, bullets/prose)
- Things they explicitly said they don't like
- Tone preferences (formal/casual, technical/simple)
- Things they asked you to always or never do

CONVERSATION:
{conversation}

Output ONLY valid JSON:
{{
  "preferences": {{"category": ["preference1", "preference2"]}},
  "dislikes": ["dislike1", "dislike2"],
  "communication_style": {{"key": "value"}}
}}

If nothing found, output: {{"preferences": {{}}, "dislikes": [], "communication_style": {{}}}}
"""

_PROJECT_EXTRACT_PROMPT = """
Analyze this conversation and identify any PROJECTS the user mentioned working on.

CONVERSATION:
{conversation}

Output ONLY a JSON array:
[{{"name": "project name", "description": "brief description"}}]

If none, output: []
"""


class TrainingEngine:
    """
    Extracts and permanently saves learnings from conversation history.
    Called by /train command.
    """

    def __init__(self, learnings: LearningsStore):
        self.learnings = learnings

    def _get_conversation_text(self, memory_manager) -> str:
        """Convert memory buffer to plain conversation text."""
        lines = []
        for msg in memory_manager.conversation_buffer[-60:]:  # last 60 msgs
            role = "USER" if msg["role"] == "user" else "AGENT"
            lines.append(f"{role}: {msg['content'][:500]}")
        return "\n".join(lines)

    def _extract_json(self, text: str, default):
        """Safely extract JSON from LLM response."""
        text = text.strip()
        # Remove markdown fences
        text = re.sub(r"```json?\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        # Find JSON
        m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return default

    def train(self, memory_manager, session_store=None) -> Dict[str, Any]:
        """
        Run full training cycle. Returns a summary of what was learned.
        """
        results = {
            "facts_added": 0,
            "topics_bumped": 0,
            "preferences_added": 0,
            "dislikes_added": 0,
            "projects_found": 0,
            "comm_style_updates": 0,
        }

        # Build conversation text
        conv = self._get_conversation_text(memory_manager)
        if not conv.strip():
            return results

        interaction_count = len([m for m in memory_manager.conversation_buffer
                                  if m["role"] == "user"])

        # ── Extract facts ─────────────────────────────────────────────────────
        try:
            raw = generate_response(
                _FACT_EXTRACT_PROMPT.format(conversation=conv[:6000]),
                provider="auto",
                system_prompt="Extract facts. Output only JSON array.",
            )
            facts = self._extract_json(raw, [])
            if isinstance(facts, list):
                for fact in facts[:20]:
                    if isinstance(fact, str) and len(fact) > 5:
                        self.learnings.add_fact(fact, confidence=0.8, source="train")
                        results["facts_added"] += 1
        except Exception:
            pass

        # ── Extract topics ────────────────────────────────────────────────────
        try:
            raw = generate_response(
                _TOPIC_EXTRACT_PROMPT.format(conversation=conv[:6000]),
                provider="auto",
                system_prompt="Extract topics. Output only JSON array.",
            )
            topics = self._extract_json(raw, [])
            if isinstance(topics, list):
                for topic in topics[:10]:
                    if isinstance(topic, str) and len(topic) > 2:
                        self.learnings.bump_topic(topic)
                        results["topics_bumped"] += 1
        except Exception:
            pass

        # ── Extract preferences ───────────────────────────────────────────────
        try:
            raw = generate_response(
                _PREFERENCE_EXTRACT_PROMPT.format(conversation=conv[:6000]),
                provider="auto",
                system_prompt="Extract preferences. Output only JSON.",
            )
            pref_data = self._extract_json(raw, {
                "preferences": {}, "dislikes": [], "communication_style": {}
            })
            if isinstance(pref_data, dict):
                for cat, prefs in pref_data.get("preferences", {}).items():
                    for p in (prefs or []):
                        if isinstance(p, str):
                            self.learnings.add_preference(cat, p)
                            results["preferences_added"] += 1
                for d in pref_data.get("dislikes", []):
                    if isinstance(d, str):
                        self.learnings.add_dislike(d)
                        results["dislikes_added"] += 1
                for k, v in pref_data.get("communication_style", {}).items():
                    if isinstance(k, str) and isinstance(v, str):
                        self.learnings.update_communication_style(k, v)
                        results["comm_style_updates"] += 1
        except Exception:
            pass

        # ── Extract projects ──────────────────────────────────────────────────
        try:
            raw = generate_response(
                _PROJECT_EXTRACT_PROMPT.format(conversation=conv[:6000]),
                provider="auto",
                system_prompt="Extract projects. Output only JSON array.",
            )
            projects = self._extract_json(raw, [])
            if isinstance(projects, list):
                for proj in projects[:5]:
                    if isinstance(proj, dict) and proj.get("name"):
                        self.learnings.add_project(
                            proj["name"],
                            proj.get("description", "")
                        )
                        results["projects_found"] += 1
        except Exception:
            pass

        # ── Mark trained ──────────────────────────────────────────────────────
        self.learnings.mark_trained(interaction_count)

        return results
