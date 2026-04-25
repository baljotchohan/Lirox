"""
Visual Designer
Picks colours, fonts, and layout style based on domain and emotional tone.
"""
import logging
from dataclasses import dataclass
from typing import Dict

from lirox.designer.domain_knowledge import DomainKnowledge

_logger = logging.getLogger("lirox.designer.visual")


@dataclass
class DesignSystem:
    """Complete visual design system for a document or site."""
    color_palette: Dict[str, str]   # primary, secondary, accent
    fonts: Dict[str, str]           # headings, body
    spacing: str                    # "tight" | "normal" | "spacious"
    style: str                      # "minimal" | "bold" | "elegant" | "balanced"


class VisualDesigner:
    """Makes aesthetic decisions informed by domain knowledge and emotional tone."""

    def design_system(self, intent) -> DesignSystem:
        """
        Return a DesignSystem that matches the domain and tone.

        Examples:
          - Gym (energetic)        → orange/black, Bebas Neue, tight/bold
          - Restaurant (elegant)   → gold/black, Playfair, spacious/elegant
          - Tech startup (modern)  → purple/teal, Inter Bold, normal/minimal
          - Sikh history (academic)→ navy/slate, Merriweather, spacious/balanced
        """
        pattern = DomainKnowledge.get_pattern(intent.domain)
        tone = intent.emotional_tone.lower()
        palettes = pattern.get("color_palettes", {})

        # Select palette whose vibe contains tone keywords
        selected = None
        for palette_data in palettes.values():
            vibe = palette_data.get("vibe", "").lower()
            if any(word in vibe for word in tone.split()):
                selected = palette_data
                break

        if not selected:
            selected = next(iter(palettes.values()), {
                "primary": "#1976D2", "secondary": "#0D47A1", "accent": "#FFFFFF"
            })

        colors = {
            "primary":   selected.get("primary",   "#1976D2"),
            "secondary": selected.get("secondary", "#0D47A1"),
            "accent":    selected.get("accent",    "#FFFFFF"),
        }

        font_opts = pattern.get("fonts", {})
        fonts = {
            "headings": font_opts.get("headings", ["Inter Bold"])[0],
            "body":     font_opts.get("body",     ["Inter"])[0],
        }

        if any(w in tone for w in ("minimal", "clean", "academic", "scholarly")):
            spacing, style = "spacious", "minimal"
        elif any(w in tone for w in ("bold", "energetic", "intense", "aggressive")):
            spacing, style = "tight", "bold"
        elif any(w in tone for w in ("elegant", "luxurious", "sophisticated")):
            spacing, style = "spacious", "elegant"
        else:
            spacing, style = "normal", "balanced"

        return DesignSystem(color_palette=colors, fonts=fonts, spacing=spacing, style=style)
