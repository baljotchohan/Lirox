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
    def generate(topic: str, query: str, file_type: str, 
                 audience: str = "general",
                 structure_hints: List[str] = None,
                 design_context: str = "") -> Dict:
        """
        Generate rich, substantive content
        
        Args:
            design_context: Design plan context (palette, theme, etc)
                            NOW ACTUALLY USED instead of ignored
        """
        
        from lirox.utils.llm import generate_response
        import re
        
        # Build FULL context for LLM
        full_context = f"""
You are creating rich, detailed content for a {file_type.upper()} document.

Topic: {topic}
Query: {query}
Audience: {audience}
Suggested Structure: {structure_hints or 'flexible'}

Design Context:
{design_context}

CRITICAL RULES:
1. NO generic placeholder text like "This section covers X in context of Y"
2. MINIMUM 300 words per section
3. INCLUDE: specific facts, dates, quotes, examples, analysis
4. STRUCTURE: intro, 3-5 detailed subsections, conclusion
5. TONE: match design context and audience
6. VALUE: reader learns something concrete

DO NOT return thin sections.
DO NOT repeat the query word for word.
DO NOT use filler text.

Generate {len(structure_hints or [])} rich sections with REAL content.
Each section should have:
- Clear heading
- Substantial body (300+ words)
- Specific examples
- Concrete takeaways
"""
        
        # Call LLM with FULL CONTEXT
        response = generate_response(
            full_context,
            provider="auto",
            system_prompt="You are an expert content creator. Generate rich, substantive content."
        )
        
        # Parse response into sections
        sections = ContentStrategist._parse_sections(response, query)
        
        # VERIFY sections are actually rich
        for i, section in enumerate(sections):
            word_count = len(section.get('body', '').split())
            if word_count < 100:
                # TOO THIN - regenerate this section
                sections[i] = ContentStrategist._regenerate_section(section, design_context)
        
        return {
            'title': topic,
            'sections': sections,
            'slides': [{'title': s.get('heading'), 'bullets': [s.get('body')[:80]], 'notes': s.get('body')} for s in sections],
            'sheets': [{'name': 'Data', 'headers': ['Heading', 'Body'], 'rows': [[s.get('heading'), s.get('body')] for s in sections]}]
        }
    
    @staticmethod
    def _regenerate_section(thin_section: Dict, design_context: str) -> Dict:
        """
        Regenerate a section that was too thin
        """
        
        from lirox.utils.llm import generate_response
        
        prompt = f"""
Previous attempt was too thin: "{thin_section.get('heading', 'Section')}"
Generated text had only {len(thin_section.get('body', '').split())} words.

REGENERATE with these requirements:
- MINIMUM 300 words
- RICH with details, facts, examples
- NO placeholder text
- ACTUAL valuable content

Design Context:
{design_context}

Heading: {thin_section.get('heading', 'Content')}
"""
        
        response = generate_response(
            prompt,
            provider="auto",
            system_prompt="Generate rich, detailed content. No filler text."
        )
        
        return {
            'heading': thin_section.get('heading', 'Content'),
            'body': response,
            'bullets': [],
        }
    
    @staticmethod
    def _parse_sections(text: str, query: str) -> List[Dict]:
        """
        Parse LLM response into structured sections
        """
        
        import re
        sections = []
        
        # Try to split on markdown headers
        parts = re.split(r'#+\s+(.+)', text)
        
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    sections.append({
                        'heading': parts[i].strip(),
                        'body': parts[i + 1].strip(),
                        'bullets': [],
                    })
        else:
            # No clear structure, use whole text
            sections.append({
                'heading': query[:80],
                'body': text,
                'bullets': [],
            })
        
        return sections

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
