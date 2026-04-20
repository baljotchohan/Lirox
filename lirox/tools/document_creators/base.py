"""Shared design system and utilities for all document creators.

Contains: color palettes, palette-picker, hex-to-RGB helper, and the
auto-install dependency helper used by every creator module.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any, Dict, List

_logger = logging.getLogger("lirox.document_creators")


# ─────────────────────────────────────────────────────────────────────────────
# Dependency auto-installer
# ─────────────────────────────────────────────────────────────────────────────

def ensure_dep(package: str, import_name: str = None):
    """Auto-install a Python package if it is not already importable."""
    import importlib
    import_name = import_name or package.replace("-", "_")
    try:
        return __import__(import_name)
    except ImportError:
        _logger.info("Installing missing dependency: %s", package)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package, "--quiet",
             "--disable-pip-version-check"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        importlib.invalidate_caches()
        return __import__(import_name)


# ─────────────────────────────────────────────────────────────────────────────
# Design System — topic-aware color palettes
# ─────────────────────────────────────────────────────────────────────────────

PALETTES: Dict[str, Dict[str, str]] = {
    "culture": {
        "primary":    "B85042",   # Terracotta
        "secondary":  "E7E8D1",   # Sand
        "accent":     "A7BEAE",   # Sage
        "text_dark":  "2D2D2D",
        "text_light": "FFFFFF",
        "bg_dark":    "3D2B1F",   # Dark brown
        "bg_light":   "FBF7F0",
    },
    "technology": {
        "primary":    "1E2761",   # Navy
        "secondary":  "CADCFC",   # Ice blue
        "accent":     "7B68EE",   # Slate blue
        "text_dark":  "1A1A2E",
        "text_light": "FFFFFF",
        "bg_dark":    "0F0F23",
        "bg_light":   "F8F9FC",
    },
    "nature": {
        "primary":    "2C5F2D",   # Forest green
        "secondary":  "97BC62",   # Moss
        "accent":     "D4E09B",   # Lime
        "text_dark":  "1B3A1B",
        "text_light": "FFFFFF",
        "bg_dark":    "1B3A1B",
        "bg_light":   "F5F9F0",
    },
    "business": {
        "primary":    "36454F",   # Charcoal
        "secondary":  "F2F2F2",   # Off-white
        "accent":     "E85D04",   # Warm orange
        "text_dark":  "212121",
        "text_light": "FFFFFF",
        "bg_dark":    "212121",
        "bg_light":   "FAFAFA",
    },
    "health": {
        "primary":    "028090",   # Teal
        "secondary":  "00A896",   # Seafoam
        "accent":     "02C39A",   # Mint
        "text_dark":  "1A1A2E",
        "text_light": "FFFFFF",
        "bg_dark":    "014451",
        "bg_light":   "F0FAFA",
    },
    "creative": {
        "primary":    "6D2E46",   # Berry
        "secondary":  "A26769",   # Dusty rose
        "accent":     "ECE2D0",   # Cream
        "text_dark":  "2D1B28",
        "text_light": "FFFFFF",
        "bg_dark":    "2D1B28",
        "bg_light":   "FCF8F3",
    },
    "education": {
        "primary":    "2B4570",   # Slate blue
        "secondary":  "A3CEF1",   # Light blue
        "accent":     "E7C582",   # Gold
        "text_dark":  "1A2744",
        "text_light": "FFFFFF",
        "bg_dark":    "1A2744",
        "bg_light":   "F5F8FC",
    },
    "default": {
        "primary":    "2563EB",   # Blue
        "secondary":  "DBEAFE",   # Light blue
        "accent":     "F59E0B",   # Amber
        "text_dark":  "1F2937",
        "text_light": "FFFFFF",
        "bg_dark":    "111827",
        "bg_light":   "F9FAFB",
    },
}

# Topic-keyword → palette mappings
_PALETTE_KEYWORDS: Dict[str, List[str]] = {
    "culture": [
        "rajasthan", "india", "culture", "history", "heritage", "travel",
        "tourism", "tradition", "ancient", "civilization", "festival",
        "art", "temple", "monument", "cuisine", "folklore", "religion",
    ],
    "technology": [
        "ai", "artificial intelligence", "machine learning", "technology",
        "software", "coding", "programming", "computer", "data science",
        "blockchain", "cybersecurity", "cloud", "devops", "api", "web",
        "algorithm", "neural", "deep learning", "automation", "iot",
    ],
    "nature": [
        "nature", "environment", "climate", "earth", "ocean", "forest",
        "wildlife", "ecology", "biodiversity", "sustainability", "green",
        "geography", "geology", "space", "astronomy", "planet",
    ],
    "business": [
        "business", "finance", "strategy", "marketing", "startup",
        "investment", "economics", "management", "corporate", "revenue",
        "growth", "leadership", "entrepreneurship", "sales", "profit",
    ],
    "health": [
        "health", "medical", "wellness", "fitness", "nutrition",
        "mental health", "medicine", "healthcare", "disease", "therapy",
        "exercise", "diet", "yoga", "mindfulness",
    ],
    "creative": [
        "art", "design", "creative", "photography", "film", "music",
        "animation", "graphic", "media", "branding", "fashion",
    ],
    "education": [
        "education", "learning", "school", "university", "student",
        "teaching", "academic", "curriculum", "course", "training",
        "study", "research", "science", "math", "physics", "chemistry",
    ],
}


def pick_palette(query: str, title: str = "") -> str:
    """Auto-select a color palette based on topic keywords in *query*/*title*."""
    combined = (query + " " + title).lower()
    best_match = "default"
    best_score = 0
    for palette_name, keywords in _PALETTE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_match = palette_name
    return best_match


def hex_to_rgb(hex_str: str):
    """Convert a 6-character hex color string to an ``RGBColor`` (python-pptx).

    Validates length so that truncated palette values cannot cause
    ``IndexError`` or silent colour corruption.
    """
    ensure_dep("python-pptx", "pptx")
    from pptx.dml.color import RGBColor
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        _logger.warning("Invalid hex colour '%s' — falling back to black", hex_str)
        hex_str = (hex_str + "000000")[:6]
    return RGBColor(int(hex_str[:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
