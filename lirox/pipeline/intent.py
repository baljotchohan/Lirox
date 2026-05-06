"""
Intent Analyzer (Pipeline Module)
Understands what user REALLY wants before creating anything.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List

from lirox.utils.llm import generate_response

_logger = logging.getLogger("lirox.pipeline.intent")


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
    length_override: bool = False      # true if user requested very short/1-page length

import re
LENGTH_OVERRIDE_PATTERNS = re.compile(
    r"\b("
    r"one[ -]?page|single[ -]?page|1[ -]?page"
    r"|brief|short|concise|quick|summary|summarize|summarise"
    r"|one[ -]?slide|single[ -]?slide|snapshot|overview only"
    r"|keep it short|keep it brief|just a summary"
    r")\b",
    re.IGNORECASE,
)

def detect_length_override(query: str) -> bool:
    """Detects if user explicitly wants a very short/single page result."""
    return bool(LENGTH_OVERRIDE_PATTERNS.search(query))


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
        """Deep analysis of what the user really wants."""
        if not isinstance(context, dict):
            _logger.warning("analyze() received context of type %s — resetting to {}",
                            type(context).__name__)
            context = {}

        # Detect explicit length overrides ("one page", "1 page", "short", etc.)
        is_short = detect_length_override(query)

        ctx_snippet = json.dumps(context, ensure_ascii=False)[:400]
        prompt = _PROMPT_TMPL.format(query=query, context=ctx_snippet)

        try:
            raw = generate_response(prompt, provider="auto", system_prompt=_SYSTEM)
            # Use the robust O(n) extractor instead of manual strip + json.loads
            from lirox.utils.llm_json import extract_json
            data = extract_json(raw)

            return IntentProfile(
                domain=data.get("domain", "general"),
                business_type=data.get("business_type", "general"),
                target_audience=data.get("target_audience", "general audience"),
                primary_purpose=data.get("primary_purpose", "information"),
                secondary_purposes=data.get("secondary_purposes", []),
                emotional_tone=data.get("emotional_tone", "professional"),
                key_actions=data.get("key_actions", []),
                constraints=data.get("constraints", {}),
                length_override=is_short,
            )

        except Exception as exc:
            _logger.warning("IntentAnalyzer failed (%s) — using fallback", exc)
            fallback = _FALLBACK_INTENT
            if is_short:
                from dataclasses import replace
                fallback = replace(fallback, length_override=True)
            return fallback
