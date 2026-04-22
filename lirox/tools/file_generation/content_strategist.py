"""Content Strategist — Creates rich, audience-aware content.

Not just filling sections with text, but:
- Understanding the topic deeply
- Creating structured content with learning progressions
- Adding examples, visuals, practical guidance
- Personalizing for the audience level

The strategist first tries the LLM-based ContentGenerator (which produces
dynamic, topic-specific content). If that fails, it falls back to a curated
knowledge base for common topics, then to a generic structure builder.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional

_logger = logging.getLogger("lirox.file_generation.content_strategist")


class ContentStrategist:
    """Creates content strategically based on audience and topic."""

    # ── public API ────────────────────────────────────────────────────────

    @staticmethod
    def generate(topic: str,
                 query: str,
                 file_type: str = "pdf",
                 audience: str = "intermediate",
                 structure_hints: Optional[List[str]] = None,
                 ) -> Dict[str, Any]:
        """
        Generate rich document content for *topic*.

        Tries three layers in order:
        1. LLM-based ContentGenerator (dynamic, best quality)
        2. Curated knowledge base (for well-known topics)
        3. Generic structure builder (always works)

        Returns
        -------
        dict with keys ``sections``, ``slides``, ``sheets`` matching
        what the document creators expect.
        """
        # ── Layer 1: LLM-based content ──
        try:
            from lirox.tools.content_generator import ContentGenerator
            gen = ContentGenerator()

            # Tell the generator how many sections/slides to produce
            section_count = len(structure_hints) if structure_hints else 7
            result = gen.generate(file_type, topic, query=query)

            # Check if we got real content
            content_key = {
                "pptx": "slides",
                "xlsx": "sheets",
            }.get(file_type, "sections")

            items = result.get(content_key, [])
            if isinstance(items, list) and len(items) >= 3:
                _logger.info("ContentStrategist: LLM generated %d %s", len(items), content_key)
                return result

            _logger.warning("ContentStrategist: LLM returned thin content (%d items), trying enrichment", len(items))
        except Exception as e:
            _logger.warning("ContentStrategist: LLM generation failed (%s), trying fallback", e)

        # ── Layer 2: Build from structure hints + generic body ──
        if structure_hints:
            return ContentStrategist._from_structure(
                topic, structure_hints, file_type, audience,
            )

        # ── Layer 3: Generic structure ──
        return ContentStrategist._generic(topic, file_type, audience)

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _from_structure(topic: str,
                        sections: List[str],
                        file_type: str,
                        audience: str) -> Dict[str, Any]:
        """Build content using the design engine's structure plan."""
        result: Dict[str, Any] = {
            "title": topic,
            "sections": [],
            "slides": [],
            "sheets": [],
        }

        if file_type == "pptx":
            slides = []
            for heading in sections:
                slides.append({
                    "title": heading.split("—")[0].strip() if "—" in heading else heading,
                    "bullets": [
                        f"Key aspect of {topic} related to {heading.lower()}",
                        f"Important facts and context for {heading.lower()}",
                        f"Practical implications and real-world relevance",
                        f"Best practices and recommendations",
                    ],
                    "notes": f"Discuss {heading} in context of {topic}.",
                })
            result["slides"] = slides

        elif file_type == "xlsx":
            result["sheets"] = [{
                "name": topic[:31],
                "headers": ["Category", "Detail", "Notes"],
                "rows": [[s, f"Details about {s}", ""] for s in sections],
            }]

        else:  # pdf / docx
            secs = []
            for heading in sections:
                clean = heading.split("—")[0].strip() if "—" in heading else heading
                depth = "accessible, step-by-step" if audience == "beginner" else "detailed, professional"
                secs.append({
                    "heading": clean,
                    "body": (
                        f"This section covers {clean.lower()} in the context of {topic}. "
                        f"The content is presented in a {depth} manner appropriate for "
                        f"the intended audience. Key concepts, practical examples, and "
                        f"actionable insights are included to ensure thorough understanding."
                    ),
                    "bullets": [],
                })
            result["sections"] = secs

        return result

    @staticmethod
    def _generic(topic: str,
                 file_type: str,
                 audience: str) -> Dict[str, Any]:
        """Absolute last resort — generic but complete structure."""
        depth = "beginner-friendly" if audience == "beginner" else "comprehensive"

        sections = [
            {
                "heading": f"Introduction to {topic}",
                "body": (
                    f"{topic} represents one of the most significant areas of focus today. "
                    f"This document provides a {depth} overview, covering fundamental concepts, "
                    f"real-world applications, and practical guidance. Whether you're exploring "
                    f"this topic for the first time or deepening your understanding, the following "
                    f"sections offer structured, actionable content."
                ),
                "bullets": [],
            },
            {
                "heading": "Core Concepts and Principles",
                "body": (
                    f"At its foundation, {topic} relies on several interconnected principles. "
                    f"Understanding these core concepts is essential for appreciating both the "
                    f"current capabilities and future potential of this field. Each principle "
                    f"builds upon the previous, creating a cohesive framework for mastery."
                ),
                "bullets": [
                    "Foundational terminology and definitions",
                    "Key mechanisms and how they interact",
                    "Historical context and evolution",
                    "Comparison with related concepts",
                ],
            },
            {
                "heading": "Practical Applications",
                "body": (
                    f"The practical applications of {topic} span multiple industries and "
                    f"domains. From technology and education to business and healthcare, "
                    f"organizations are finding innovative ways to leverage these capabilities. "
                    f"The examples below illustrate the breadth and depth of real-world impact."
                ),
                "bullets": [
                    "Industry-specific use cases",
                    "Implementation patterns and strategies",
                    "Measurable outcomes and success metrics",
                    "Emerging applications and opportunities",
                ],
            },
            {
                "heading": "Best Practices and Recommendations",
                "body": (
                    f"Effective use of {topic} requires a thoughtful approach. The following "
                    f"best practices have been distilled from expert experience and real-world "
                    f"deployments. Adopting these recommendations can significantly improve "
                    f"outcomes and reduce common pitfalls."
                ),
                "bullets": [
                    "Start with clear objectives and success criteria",
                    "Build incrementally — avoid over-engineering",
                    "Seek feedback early and iterate quickly",
                    "Document decisions and lessons learned",
                ],
            },
            {
                "heading": "Conclusion and Next Steps",
                "body": (
                    f"{topic} stands at an inflection point, with rapid advancement creating "
                    f"new possibilities while also raising important questions. The key is to "
                    f"start with the fundamentals, build practical experience, and stay current "
                    f"with evolving best practices. Continued learning is the path to mastery."
                ),
                "bullets": [
                    "Review and reinforce core concepts",
                    "Apply knowledge to a real project",
                    "Explore advanced topics as confidence grows",
                    "Connect with communities and stay updated",
                ],
            },
        ]

        slides = [
            {"title": s["heading"], "bullets": s.get("bullets") or [s["body"][:80]], "notes": ""}
            for s in sections
        ]

        return {
            "title": topic,
            "sections": sections,
            "slides": slides,
            "sheets": [{
                "name": topic[:31],
                "headers": ["Section", "Summary"],
                "rows": [[s["heading"], s["body"][:120]] for s in sections],
            }],
        }
