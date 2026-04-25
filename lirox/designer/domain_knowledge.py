"""
Domain Knowledge Database
Industry-specific patterns, colours, and trust signals.
"""
from __future__ import annotations

INDUSTRY_PATTERNS = {
    "fitness": {
        "essential_sections": ["hero", "classes", "trainers", "pricing", "results", "contact"],
        "color_palettes": {
            "power":    {"primary": "#FF0000", "secondary": "#000000", "accent": "#FFFFFF",
                         "vibe": "intense aggressive strength"},
            "energy":   {"primary": "#FF6B00", "secondary": "#FFC107", "accent": "#212121",
                         "vibe": "energetic motivating dynamic"},
            "wellness": {"primary": "#00BFA5", "secondary": "#FFFFFF", "accent": "#263238",
                         "vibe": "balanced healthy calm"},
        },
        "fonts": {"headings": ["Bebas Neue", "Oswald", "Montserrat Bold"],
                  "body":     ["Inter", "Roboto", "Open Sans"]},
        "trust_signals": ["trainer credentials", "member testimonials", "facility photos", "results"],
        "cta_priority":  ["Book Free Trial", "View Schedule", "Join Now"],
        "user_journey":  ["discover", "interest", "trial", "signup"],
    },

    "restaurant": {
        "essential_sections": ["hero", "menu", "chef_story", "location", "reservations"],
        "color_palettes": {
            "elegant": {"primary": "#1A1A1A", "secondary": "#D4AF37", "accent": "#FFFFFF",
                        "vibe": "sophisticated upscale elegant"},
            "rustic":  {"primary": "#5D4037", "secondary": "#FF6F00", "accent": "#FFF8E1",
                        "vibe": "warm homey authentic rustic"},
            "modern":  {"primary": "#212121", "secondary": "#FF5722", "accent": "#FAFAFA",
                        "vibe": "contemporary fresh modern"},
        },
        "fonts": {"headings": ["Playfair Display", "Cormorant", "Libre Baskerville"],
                  "body":     ["Lato", "Raleway", "Source Sans Pro"]},
        "trust_signals": ["chef bio", "reviews", "food photos", "awards"],
        "cta_priority":  ["Make Reservation", "Order Online", "View Menu"],
        "user_journey":  ["discover", "menu_browse", "decision", "reservation"],
    },

    "tech_startup": {
        "essential_sections": ["hero", "problem", "solution", "features", "pricing", "team"],
        "color_palettes": {
            "innovation": {"primary": "#6200EA", "secondary": "#00BFA5", "accent": "#FFFFFF",
                           "vibe": "innovative cutting-edge"},
            "trust":      {"primary": "#1976D2", "secondary": "#0D47A1", "accent": "#E3F2FD",
                           "vibe": "reliable professional trustworthy"},
            "bold":       {"primary": "#D50000", "secondary": "#212121", "accent": "#FFFFFF",
                           "vibe": "disruptive confident bold"},
        },
        "fonts": {"headings": ["Inter Bold", "Poppins", "Space Grotesk"],
                  "body":     ["Inter", "Work Sans", "IBM Plex Sans"]},
        "trust_signals": ["customer logos", "metrics", "testimonials", "security badges"],
        "cta_priority":  ["Start Free Trial", "Book Demo", "Get Started"],
        "user_journey":  ["awareness", "evaluation", "trial", "adoption"],
    },

    "ecommerce": {
        "essential_sections": ["hero", "featured_products", "categories", "testimonials", "trust_badges"],
        "color_palettes": {
            "modern":  {"primary": "#212121", "secondary": "#FF5722", "accent": "#FAFAFA",
                        "vibe": "clean contemporary modern"},
            "playful": {"primary": "#E91E63", "secondary": "#9C27B0", "accent": "#FFFFFF",
                        "vibe": "fun vibrant playful energetic"},
            "luxury":  {"primary": "#1A1A1A", "secondary": "#D4AF37", "accent": "#FFFFFF",
                        "vibe": "premium exclusive luxury"},
        },
        "fonts": {"headings": ["Montserrat", "Raleway", "Poppins"],
                  "body":     ["Open Sans", "Lato", "Nunito"]},
        "trust_signals": ["customer reviews", "secure checkout", "return policy", "shipping info"],
        "cta_priority":  ["Shop Now", "Add to Cart", "View Collection"],
        "user_journey":  ["browse", "product_view", "cart", "checkout"],
    },

    "professional_services": {
        "essential_sections": ["hero", "services", "expertise", "case_studies", "contact"],
        "color_palettes": {
            "corporate":   {"primary": "#1565C0", "secondary": "#0D47A1", "accent": "#E3F2FD",
                            "vibe": "professional trustworthy corporate"},
            "modern_pro":  {"primary": "#263238", "secondary": "#00BFA5", "accent": "#FFFFFF",
                            "vibe": "modern competent professional"},
            "executive":   {"primary": "#1A1A1A", "secondary": "#616161", "accent": "#FFFFFF",
                            "vibe": "authoritative premium executive"},
        },
        "fonts": {"headings": ["Merriweather", "Lora", "Playfair Display"],
                  "body":     ["Open Sans", "Lato", "Source Sans Pro"]},
        "trust_signals": ["credentials", "case studies", "client logos", "certifications"],
        "cta_priority":  ["Schedule Consultation", "Get Quote", "Contact Us"],
        "user_journey":  ["research", "evaluation", "consultation", "engagement"],
    },

    "educational": {
        "essential_sections": ["introduction", "background", "main_content", "analysis", "conclusion"],
        "color_palettes": {
            "academic": {"primary": "#1A237E", "secondary": "#283593", "accent": "#E8EAF6",
                         "vibe": "academic scholarly authoritative"},
            "modern":   {"primary": "#37474F", "secondary": "#546E7A", "accent": "#ECEFF1",
                         "vibe": "clean readable modern minimal"},
        },
        "fonts": {"headings": ["Merriweather", "Georgia", "Palatino"],
                  "body":     ["Source Serif Pro", "Lora", "Open Sans"]},
        "trust_signals": ["citations", "data", "expert quotes", "bibliography"],
        "cta_priority":  ["Read More", "Explore Sources", "Learn Further"],
        "user_journey":  ["read", "understand", "explore", "apply"],
    },
}

_DEFAULT_PATTERN = {
    "essential_sections": ["introduction", "content", "conclusion"],
    "color_palettes": {
        "professional": {"primary": "#1976D2", "secondary": "#0D47A1", "accent": "#E3F2FD",
                         "vibe": "professional clean"},
    },
    "fonts": {"headings": ["Inter Bold", "Roboto", "Open Sans"],
              "body":     ["Inter", "Roboto", "Open Sans"]},
    "trust_signals": ["testimonials", "credentials"],
    "cta_priority":  ["Contact Us", "Learn More"],
    "user_journey":  ["discover", "learn", "engage"],
}


class DomainKnowledge:
    """Access industry-specific patterns."""

    @staticmethod
    def get_pattern(domain: str) -> dict:
        """Return the best-matching pattern for a domain string."""
        d = domain.lower()

        # Direct match
        if d in INDUSTRY_PATTERNS:
            return INDUSTRY_PATTERNS[d]

        # Substring match
        for key, pattern in INDUSTRY_PATTERNS.items():
            if key in d or d in key:
                return pattern

        # Semantic heuristics
        if any(w in d for w in ("history", "biography", "religion", "philosophy",
                                 "culture", "academic", "research", "study")):
            return INDUSTRY_PATTERNS["educational"]

        if any(w in d for w in ("software", "app", "saas", "tech", "api", "startup")):
            return INDUSTRY_PATTERNS["tech_startup"]

        if any(w in d for w in ("shop", "store", "product", "retail", "market")):
            return INDUSTRY_PATTERNS["ecommerce"]

        if any(w in d for w in ("gym", "workout", "fitness", "health club", "sport")):
            return INDUSTRY_PATTERNS["fitness"]

        if any(w in d for w in ("restaurant", "cafe", "bar", "food", "dining", "kitchen")):
            return INDUSTRY_PATTERNS["restaurant"]

        return _DEFAULT_PATTERN
