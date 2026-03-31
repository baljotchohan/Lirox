"""
Lirox v0.6 — API Tier System

Controls which research APIs are available based on what keys the user has
configured. All keys live in .env and are never exposed to users.

TIER 0 (no paid keys): DuckDuckGo only
TIER 1 (one paid search key): Tavily OR Serper OR Exa
TIER 2 (multiple paid keys): All APIs in parallel, highest quality
"""

import os

SEARCH_APIS = {
    "tavily":  "TAVILY_API_KEY",
    "serper":  "SERPER_API_KEY",
    "exa":     "EXA_API_KEY",
}


def get_available_search_apis() -> list:
    """Return list of search API names that have keys configured."""
    return [name for name, env_var in SEARCH_APIS.items() if os.getenv(env_var)]


def get_tier() -> int:
    """
    Returns current research tier:
      0 = no paid search APIs (DuckDuckGo fallback only)
      1 = one paid search API
      2 = two or more paid search APIs
    """
    available = get_available_search_apis()
    if len(available) >= 2:
        return 2
    elif len(available) == 1:
        return 1
    return 0


def tier_description() -> str:
    """Human-readable current tier description."""
    tier = get_tier()
    apis = get_available_search_apis()
    if tier == 0:
        return "Tier 0 (Free) — DuckDuckGo search only. Add Tavily/Serper/Exa keys for better research."
    elif tier == 1:
        return f"Tier 1 (Standard) — {apis[0].title()} search active."
    else:
        return f"Tier 2 (Premium) — {', '.join(a.title() for a in apis)} active. Maximum research quality."


def can_access_feature(feature: str) -> bool:
    """Check if a specific feature is available based on current tier."""
    tier = get_tier()
    FEATURE_TIERS = {
        "deep_research":   1,   # Requires at least one paid search API
        "parallel_search": 2,   # Requires 2+ APIs
        "exa_neural":      1,   # Requires Exa specifically
        "google_results":  1,   # Requires Serper
    }
    required = FEATURE_TIERS.get(feature, 0)
    return tier >= required
