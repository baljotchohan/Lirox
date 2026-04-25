"""
Content Writer
Writes actual domain-relevant content, one section at a time.

Core fix: Generates section-by-section to prevent the "same paragraph 20x" bug.
"""
import logging

from lirox.utils.llm import generate_response

_logger = logging.getLogger("lirox.designer.content")

_WRITER_SYSTEM = (
    "You are an expert copywriter. Write compelling, domain-specific content. "
    "Be concrete and factual. No Lorem ipsum. No generic business clichés. "
    "Output ONLY the section text — no headings, no preamble."
)

_SECTION_PROMPT = """\
Write the '{section_name}' section for a {domain} document.

Section purpose: {purpose}
Target audience: {audience}
Emotional tone: {tone}
Domain: {domain}

Requirements:
- 3-5 paragraphs (400-700 words total)
- Be SPECIFIC to {domain} — use real terminology, examples, and facts
- Match the {tone} tone throughout
- NO filler phrases ("leading provider", "quality service", "world-class")
- NO Lorem ipsum or placeholder text
- NO markdown headings or bullet points (pure prose)
{avoid_clause}

Write the section content now:
"""


class ContentWriter:
    """Writes one section at a time with domain expertise."""

    def write_section(
        self,
        section_name: str,
        section_purpose: str,
        intent,
        section_index: int,
        avoid_phrases: str = "",
    ) -> str:
        """
        Generate content for exactly ONE section.

        Accepts an optional avoid_phrases string to prevent repetition
        when regenerating after similarity detection.
        """
        avoid_clause = (
            f"\nDO NOT repeat or paraphrase these phrases:\n{avoid_phrases[:400]}"
            if avoid_phrases
            else ""
        )

        prompt = _SECTION_PROMPT.format(
            section_name=section_name,
            purpose=section_purpose,
            audience=intent.target_audience,
            tone=intent.emotional_tone,
            domain=intent.domain,
            avoid_clause=avoid_clause,
        )

        content = generate_response(prompt, provider="auto", system_prompt=_WRITER_SYSTEM)

        # Strip any stray markdown that leaked through
        content = content.replace("**", "").replace("__", "").replace("##", "").strip()

        return content
