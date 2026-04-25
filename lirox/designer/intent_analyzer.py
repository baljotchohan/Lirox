"""
Intent Analyzer
Understands what user REALLY wants before creating anything.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List

from lirox.utils.llm import generate_response

_logger = logging.getLogger("lirox.designer.intent")


@dataclass
class IntentProfile:
    """User's real intent extracted from their query."""
    domain: str                        # "fitness", "restaurant", "tech", "sikh history", etc.
    business_type: str                 # "local_service", "ecommerce", "saas", "educational"
    target_audience: str               # who will read/use this
    primary_purpose: str               # "membership_signup", "information", "research"
    secondary_purposes: List[str]
    emotional_tone: str                # "energetic", "professional", "academic"
    key_actions: List[str]             # top CTAs
    constraints: Dict                  # explicit user requirements


_FALLBACK_INTENT = IntentProfile(
    domain="general",
    business_type="general",
    target_audience="general audience",
    primary_purpose="information",
    secondary_purposes=[],
    emotional_tone="professional",
    key_actions=[],
    constraints={},
)

_SYSTEM = (
    "You are a senior business analyst. Analyse the user request and extract intent precisely. "
    "Output valid JSON only — no markdown, no commentary."
)

_PROMPT_TMPL = """\
Analyse this request to understand the user's TRUE intent:

User Request: {query}
Context: {context}

Extract:
1. DOMAIN: What field/industry? (be specific, e.g. "Sikh history", "fitness gym", "SaaS startup")
2. BUSINESS_TYPE: "local_service" | "ecommerce" | "saas" | "portfolio" | "educational" | "research" | "personal"
3. TARGET_AUDIENCE: Who will read/use this?
4. PRIMARY_PURPOSE: Main goal (e.g. "membership_signup", "historical reference", "sales")
5. SECONDARY_PURPOSES: Other goals (list)
6. EMOTIONAL_TONE: Desired feeling ("professional", "energetic", "academic", "luxurious", "warm")
7. KEY_ACTIONS: Top 3 things the reader should do/take away
8. CONSTRAINTS: Any explicit user requirements (format, colours, style)

Respond with JSON only:
{{
  "domain": "...",
  "business_type": "...",
  "target_audience": "...",
  "primary_purpose": "...",
  "secondary_purposes": ["..."],
  "emotional_tone": "...",
  "key_actions": ["...", "...", "..."],
  "constraints": {{}}
}}
"""


class IntentAnalyzer:
    """Analyses a user query to produce an IntentProfile."""

    def analyze(self, query: str, context: Dict) -> IntentProfile:
        """
        Deep analysis of what the user really wants.

        Example — "Create a PDF about Sikh history":
          domain="Sikh history", business_type="educational",
          emotional_tone="academic", key_actions=["learn", "understand"]
          → NO tech/developer context injected
        """
        # SAFETY: context must be a dict for json.dumps to work
        if not isinstance(context, dict):
            _logger.warning("analyze() received context of type %s — resetting to {}",
                            type(context).__name__)
            context = {}

        ctx_snippet = json.dumps(context, ensure_ascii=False)[:400]
        prompt = _PROMPT_TMPL.format(query=query, context=ctx_snippet)

        try:
            raw = generate_response(prompt, provider="auto", system_prompt=_SYSTEM)
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            return IntentProfile(
                domain=data.get("domain", "general"),
                business_type=data.get("business_type", "general"),
                target_audience=data.get("target_audience", "general audience"),
                primary_purpose=data.get("primary_purpose", "information"),
                secondary_purposes=data.get("secondary_purposes", []),
                emotional_tone=data.get("emotional_tone", "professional"),
                key_actions=data.get("key_actions", []),
                constraints=data.get("constraints", {}),
            )

        except (json.JSONDecodeError, Exception) as exc:
            _logger.warning("IntentAnalyzer failed (%s) — using fallback", exc)
            return _FALLBACK_INTENT
