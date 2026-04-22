"""Design Engine — Topic-aware design strategy system.

Makes real design decisions based on:
- Topic/subject matter
- Audience/learner level
- File type (pdf/docx/pptx/xlsx)
- Available design patterns

This replaces the old "keyword → palette" approach with genuine
multi-signal analysis that considers the full context of a request.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

_logger = logging.getLogger("lirox.file_generation.design_engine")


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class AudienceLevel(Enum):
    """Who are we designing for?"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class DocumentFormat(Enum):
    """What format are we creating?"""
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"


class DesignTheme(Enum):
    """Visual design themes — each maps to a colour palette in base.py."""
    PROFESSIONAL = "professional"
    EDUCATIONAL = "educational"
    CREATIVE = "creative"
    MINIMAL = "minimal"
    CORPORATE = "corporate"


# ─────────────────────────────────────────────────────────────────────────────
# Design Plan (output of the engine)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DesignPlan:
    """Complete design strategy for a document."""
    topic: str
    audience: AudienceLevel
    file_type: DocumentFormat
    theme: DesignTheme
    palette: str                        # key into base.PALETTES
    structure: List[str] = field(default_factory=list)   # section names
    page_count: int = 8
    has_visuals: bool = False
    style_guide: Dict[str, Any] = field(default_factory=dict)
    color_scheme: Dict[str, str] = field(default_factory=dict)
    typography: Dict[str, str] = field(default_factory=dict)

    # ── helpers ──
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "audience": self.audience.value,
            "file_type": self.file_type.value,
            "theme": self.theme.value,
            "palette": self.palette,
            "structure": self.structure,
            "page_count": self.page_count,
            "has_visuals": self.has_visuals,
            "colors": self.color_scheme,
            "typography": self.typography,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Keyword pools for multi-signal analysis
# ─────────────────────────────────────────────────────────────────────────────

_SUBJECT_SIGNALS: Dict[str, List[str]] = {
    "educational": [
        "learn", "teach", "beginner", "tutorial", "guide", "course",
        "student", "study", "class", "lesson", "curriculum", "training",
    ],
    "technical": [
        "code", "algorithm", "tech", "software", "api", "programming",
        "machine learning", "neural", "data", "ai", "artificial intelligence",
        "python", "javascript", "system", "architecture", "cloud", "devops",
        "cybersecurity", "blockchain", "iot", "database", "web", "git",
        "github", "docker", "kubernetes", "linux", "engineering",
    ],
    "creative": [
        "design", "art", "creative", "visual", "photography", "film",
        "music", "animation", "branding", "fashion", "media",
    ],
    "business": [
        "business", "finance", "strategy", "marketing", "startup",
        "investment", "economics", "management", "corporate", "revenue",
        "growth", "leadership", "sales", "profit", "company",
    ],
    "science": [
        "physics", "chemistry", "biology", "research", "experiment",
        "scientific", "quantum", "energy", "medicine", "health",
        "ecology", "environment", "climate", "nature", "wildlife",
    ],
    "culture": [
        "history", "heritage", "tradition", "civilization", "art",
        "literature", "society", "culture", "ancient", "museum",
        "religion", "festival", "folklore",
    ],
}

_COMPLEXITY_SIGNALS = {
    "simple": [
        "beginner", "intro", "basics", "simple", "easy", "new learner",
        "newbie", "first time", "getting started", "101",
    ],
    "advanced": [
        "advanced", "expert", "professional", "deep dive", "enterprise",
        "production", "architecture", "optimization", "at scale",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# The Engine
# ─────────────────────────────────────────────────────────────────────────────

class DesignEngine:
    """Real design thinking — makes strategic design decisions."""

    # ── topic analysis ────────────────────────────────────────────────────

    @staticmethod
    def analyze_topic(query: str, title: str = "") -> Tuple[str, str, str]:
        """
        Multi-signal topic analysis.

        Returns
        -------
        (subject, complexity, suggested_theme)
        """
        combined = (query + " " + title).lower()

        # Score each subject area
        scores: Dict[str, int] = {}
        for subject, keywords in _SUBJECT_SIGNALS.items():
            score = sum(1 for kw in keywords if kw in combined)
            scores[subject] = score

        best = max(scores, key=scores.get) if max(scores.values()) > 0 else "general"

        # ── special-case overrides ──
        # "history of AI" should stay technical, not flip to culture
        if best == "culture" and scores.get("technical", 0) > 0:
            best = "technical"
        # "github for learners" → educational, not just technical
        if scores.get("educational", 0) >= 2:
            best = "educational"

        # Complexity
        complexity = "moderate"
        for level, kws in _COMPLEXITY_SIGNALS.items():
            if any(kw in combined for kw in kws):
                complexity = level
                break

        # Theme mapping
        theme_map = {
            "educational": "educational",
            "technical": "professional",
            "creative": "creative",
            "business": "corporate",
            "science": "professional",
            "culture": "creative",
            "general": "minimal",
        }
        theme = theme_map.get(best, "professional")

        return best, complexity, theme

    # ── audience inference ────────────────────────────────────────────────

    @staticmethod
    def infer_audience(query: str) -> AudienceLevel:
        """Determine audience expertise level from query signals."""
        q = query.lower()
        if any(w in q for w in [
            "beginner", "newbie", "new learner", "intro", "basics",
            "getting started", "101", "for kids", "first time",
        ]):
            return AudienceLevel.BEGINNER
        if any(w in q for w in [
            "advanced", "expert", "professional", "enterprise",
            "deep dive", "at scale", "production",
        ]):
            return AudienceLevel.ADVANCED
        if any(w in q for w in ["expert", "phd", "research level"]):
            return AudienceLevel.EXPERT
        return AudienceLevel.INTERMEDIATE

    # ── file type detection ───────────────────────────────────────────────

    @staticmethod
    def detect_file_type(query: str) -> str:
        """Return pdf / docx / pptx / xlsx."""
        q = query.lower()
        if any(w in q for w in ["ppt", "pptx", "powerpoint", "presentation", "slide", "deck"]):
            return "pptx"
        if any(w in q for w in ["excel", "xlsx", "spreadsheet", "xls"]):
            return "xlsx"
        if any(w in q for w in ["word", "docx", "doc"]):
            return "docx"
        return "pdf"

    # ── structure planning ────────────────────────────────────────────────

    @staticmethod
    def plan_structure(audience: AudienceLevel,
                       file_type: str,
                       subject: str) -> Tuple[List[str], int]:
        """Build section names and page estimate based on audience + type."""

        if file_type == "pptx":
            # slides, not pages
            if audience == AudienceLevel.BEGINNER:
                return [
                    "Title Slide",
                    "What is this?",
                    "Why does it matter?",
                    "Key Concepts (Simplified)",
                    "Getting Started (Step by Step)",
                    "Your First Project",
                    "Common Mistakes to Avoid",
                    "Tips & Tricks",
                    "Resources for Learning",
                    "Summary & Next Steps",
                ], 10
            elif audience == AudienceLevel.ADVANCED:
                return [
                    "Title Slide",
                    "Executive Overview",
                    "Technical Architecture",
                    "Advanced Patterns",
                    "Performance & Scale",
                    "Case Studies",
                    "Best Practices",
                    "Q&A / Discussion",
                ], 8
            else:
                return [
                    "Title Slide",
                    "Introduction",
                    "Core Concepts",
                    "Implementation",
                    "Advanced Techniques",
                    "Practical Applications",
                    "Troubleshooting",
                    "Conclusion",
                ], 8
        else:
            # pdf / docx sections
            if audience == AudienceLevel.BEGINNER:
                return [
                    "Introduction — What is this?",
                    "Fundamentals — Key Concepts",
                    "Getting Started — First Steps",
                    "Practical Examples — Real-world Use",
                    "Common Mistakes — What to Avoid",
                    "Tips & Tricks — Pro Tips",
                    "Summary — Key Takeaways",
                    "Next Steps — Where to Go",
                ], 10
            elif audience in (AudienceLevel.ADVANCED, AudienceLevel.EXPERT):
                return [
                    "Executive Summary",
                    "Technical Overview",
                    "Advanced Concepts",
                    "Architecture Patterns",
                    "Performance Optimization",
                    "Case Studies",
                    "Best Practices",
                    "References",
                ], 12
            else:
                return [
                    "Introduction",
                    "Core Concepts",
                    "Implementation Guide",
                    "Advanced Techniques",
                    "Practical Applications",
                    "Troubleshooting",
                    "Conclusion",
                ], 8

    # ── colour schemes ────────────────────────────────────────────────────

    _PALETTE_LOOKUP: Dict[str, str] = {
        "educational": "education",
        "technical": "technology",
        "creative": "creative",
        "business": "business",
        "corporate": "business",
        "science": "technology",
        "culture": "culture",
        "general": "default",
    }

    _COLOR_SCHEMES: Dict[str, Dict[str, str]] = {
        "technology": {"primary": "1E2761", "secondary": "CADCFC", "accent": "7B68EE"},
        "education":  {"primary": "2B4570", "secondary": "A3CEF1", "accent": "E7C582"},
        "creative":   {"primary": "6D2E46", "secondary": "A26769", "accent": "ECE2D0"},
        "business":   {"primary": "36454F", "secondary": "F2F2F2", "accent": "E85D04"},
        "culture":    {"primary": "B85042", "secondary": "E7E8D1", "accent": "A7BEAE"},
        "nature":     {"primary": "2C5F2D", "secondary": "97BC62", "accent": "D4E09B"},
        "health":     {"primary": "028090", "secondary": "00A896", "accent": "02C39A"},
        "default":    {"primary": "2563EB", "secondary": "DBEAFE", "accent": "F59E0B"},
    }

    # ── main entry point ──────────────────────────────────────────────────

    @staticmethod
    def plan_document(query: str,
                      title: str = "",
                      file_type: str | None = None) -> DesignPlan:
        """
        Create a complete design plan for the document.

        This is where DESIGN THINKING happens, not template filling.
        """
        # 1. File type
        ft = file_type or DesignEngine.detect_file_type(query)

        # 2. Topic analysis
        subject, complexity, theme = DesignEngine.analyze_topic(query, title)
        audience = DesignEngine.infer_audience(query)

        # 3. Palette from subject
        palette = DesignEngine._PALETTE_LOOKUP.get(subject, "default")
        colors = DesignEngine._COLOR_SCHEMES.get(palette, DesignEngine._COLOR_SCHEMES["default"])

        # 4. Structure
        structure, page_count = DesignEngine.plan_structure(audience, ft, subject)

        # 5. Typography & style
        typography = {
            "heading": "Georgia" if subject == "creative" else "Calibri",
            "body": "Calibri",
            "code": "Courier New",
            "heading_size": str(28 if audience == AudienceLevel.BEGINNER else 24),
            "body_size": "11",
        }

        style_guide = {
            "spacing": "generous" if audience == AudienceLevel.BEGINNER else "tight",
            "visual_density": "low" if audience == AudienceLevel.BEGINNER else "medium",
            "has_examples": True,
            "has_code": subject in ("technical",),
            "has_visuals": audience == AudienceLevel.BEGINNER or subject == "creative",
        }

        plan = DesignPlan(
            topic=title or query[:80],
            audience=audience,
            file_type=DocumentFormat[ft.upper()],
            theme=DesignTheme[theme.upper()],
            palette=palette,
            structure=structure,
            page_count=page_count,
            has_visuals=style_guide["has_visuals"],
            style_guide=style_guide,
            color_scheme=colors,
            typography=typography,
        )

        _logger.info(
            "Design plan: %s → %s theme, %s palette, %d sections, audience=%s",
            subject, theme, palette, len(structure), audience.value,
        )
        return plan

    # ── human-readable report ─────────────────────────────────────────────

    @staticmethod
    def log_design_decision(plan: DesignPlan) -> str:
        """Create a human-readable explanation of design choices."""
        lines = [
            "🎨 **Design Strategy**",
            f"  📖 Topic: {plan.topic}",
            f"  👥 Audience: {plan.audience.value.capitalize()}",
            f"  🎭 Theme: {plan.theme.value.capitalize()}",
            f"  🎨 Palette: {plan.palette.capitalize()}",
            f"  📑 Structure: {len(plan.structure)} sections, ~{plan.page_count} pages",
            f"  🖼️ Visuals: {'Yes' if plan.has_visuals else 'Text-focused'}",
        ]
        return "\n".join(lines)
