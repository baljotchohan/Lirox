"""Lirox v1.0 — Fact Extractor

Extracts structured knowledge (facts, preferences, topics, projects)
from raw conversation text using the configured LLM provider.

Works without a database — returns plain Python dataclasses.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

_logger = logging.getLogger("lirox.learning.extractor")

_EXTRACT_SYSTEM = (
    "You extract structured knowledge from conversations. "
    "Output ONLY valid JSON — no prose, no markdown fences."
)

_EXTRACT_PROMPT = """Analyze this conversation and extract stable knowledge about the user.

CONVERSATION:
{conversation}

Output ONLY one JSON object:
{{
  "facts": ["stable fact about the user, max 150 chars each"],
  "topics": ["specific topics discussed, max 10"],
  "preferences": {{"category": ["preference_1", "preference_2"]}},
  "dislikes": ["thing user dislikes"],
  "projects": [{{"name": "Project", "description": "one line description"}}]
}}

Rules:
- Only include clearly stated information (no guessing).
- Be specific: "Uses Python + FastAPI" not just "codes".
- Empty arrays are fine if nothing relevant was said.
"""


@dataclass
class ExtractedKnowledge:
    """Structured knowledge extracted from a conversation."""
    facts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    preferences: Dict[str, List[str]] = field(default_factory=dict)
    dislikes: List[str] = field(default_factory=list)
    projects: List[Dict[str, str]] = field(default_factory=list)
    raw_response: str = ""
    error: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.facts or self.topics or self.preferences
                    or self.dislikes or self.projects)

    @property
    def total_items(self) -> int:
        pref_count = sum(len(v) for v in self.preferences.values())
        return len(self.facts) + len(self.topics) + pref_count + len(self.projects)


class FactExtractor:
    """Extract structured knowledge from conversation text.

    Example::

        extractor = FactExtractor()
        knowledge = extractor.extract("User: I use Python daily\\nAssistant: Great!")
        print(knowledge.facts)
    """

    def __init__(self, provider: str = "auto"):
        self._provider = provider

    def extract(self, conversation: str) -> ExtractedKnowledge:
        """Extract knowledge from *conversation* text.

        Args:
            conversation: Multi-line conversation string (role: content format).

        Returns:
            :class:`ExtractedKnowledge` — always returned, check ``.error``.
        """
        if not conversation.strip():
            return ExtractedKnowledge(error="Empty conversation")

        prompt = _EXTRACT_PROMPT.format(
            conversation=conversation[:6000]
        )

        try:
            from lirox.utils.llm import generate_response
            raw = generate_response(
                prompt,
                provider=self._provider,
                system_prompt=_EXTRACT_SYSTEM,
            )
        except Exception as exc:
            return ExtractedKnowledge(error=str(exc))

        parsed, error = _parse_json(raw)
        if error:
            return ExtractedKnowledge(raw_response=raw, error=error)

        return ExtractedKnowledge(
            facts=_str_list(parsed.get("facts")),
            topics=_str_list(parsed.get("topics")),
            preferences=_str_dict_list(parsed.get("preferences")),
            dislikes=_str_list(parsed.get("dislikes")),
            projects=_project_list(parsed.get("projects")),
            raw_response=raw,
        )


# ── JSON parsing helpers ─────────────────────────────────────────────────────

def _parse_json(text: str) -> tuple[Dict[str, Any], str]:
    """Extract and parse the first JSON object from *text*."""
    text = text.strip()
    # Strip markdown fences
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            break
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Find JSON object boundaries
    start = text.find("{")
    if start == -1:
        return {}, "No JSON object found in response"
    end = text.rfind("}")
    if end == -1:
        return {}, "Unclosed JSON object in response"
    text = text[start: end + 1]

    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return {}, f"JSON parse error: {exc}"


def _str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if v and str(v).strip()]


def _str_dict_list(value: Any) -> Dict[str, List[str]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(k): _str_list(v)
        for k, v in value.items()
        if k and isinstance(v, list)
    }


def _project_list(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            result.append({
                "name": str(item.get("name", "")).strip(),
                "description": str(item.get("description", "")).strip(),
            })
    return result
