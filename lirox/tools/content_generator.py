"""ContentGenerator — LLM-based rich content generation for documents.

Generates structured, detailed content for each document format.  The
generator asks the LLM to produce content that meets minimum quality
standards (word counts, bullet counts, etc.) before the file is built.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("lirox.tools.content_generator")


class ContentGenerator:
    """Generate rich document content using an LLM.

    All methods return the same structured dict that
    ``PersonalAgent._filegen`` expects, so this class can be dropped in as
    a content enrichment step without changing the caller.
    """

    def __init__(self, llm_fn=None):
        """
        Parameters
        ----------
        llm_fn: callable(prompt, system_prompt) -> str
            The LLM function to use.  If None, falls back to
            ``lirox.utils.llm.generate_response``.
        """
        self._llm = llm_fn

    def _call_llm(self, prompt: str, system_prompt: str = "") -> str:
        if self._llm:
            return self._llm(prompt, system_prompt)
        from lirox.utils.llm import generate_response
        return generate_response(
            prompt, provider="auto",
            system_prompt=system_prompt or "Expert content writer. Output only the requested content.",
        )

    # ── Slide content ────────────────────────────────────────────────────────

    def generate_slides(self, topic: str, num_slides: int = 8,
                        context: str = "") -> List[Dict[str, Any]]:
        """Generate *num_slides* content slides for a PPTX presentation.

        Each slide dict has ``title``, ``bullets`` (4-6 items), and
        ``notes`` (speaker notes).
        """
        prompt = f"""Generate exactly {num_slides} presentation slides for the topic: "{topic}"
{('Additional context: ' + context) if context else ''}

Rules:
- Each slide must have a UNIQUE, specific, descriptive title (not generic like "Overview")
- Each slide must have 4-6 DETAILED bullet points
- Each bullet must be a COMPLETE sentence with specific facts, numbers, or examples
- Include at least 3 real statistics or data points across all slides
- Vary the content type: history, key concepts, real-world examples, data/stats, challenges, future trends
- Speaker notes should add 2-3 sentences of context not shown on the slide
- Do NOT use generic filler like "This is important" or "Many people use this"
- Be SPECIFIC: use real company names, real numbers, real dates, real examples

Output as a JSON array with {num_slides} objects, each:
{{"title": "Specific Descriptive Title", "bullets": ["Detailed point with specific fact...", "Another detailed point..."], "notes": "Speaker note with extra context..."}}

Output ONLY the JSON array, no other text."""

        raw = self._call_llm(
            prompt,
            "Expert presentation designer. Output ONLY valid JSON.",
        )
        return self._parse_list(raw, "slides", num_slides, topic)

    # ── Section content ──────────────────────────────────────────────────────

    def generate_sections(self, topic: str, num_sections: int = 5,
                          context: str = "") -> List[Dict[str, Any]]:
        """Generate *num_sections* content sections for a PDF or DOCX.

        Each section dict has ``heading``, ``body`` (3-5 sentences), and
        ``bullets`` (0-4 supporting points).
        """
        prompt = f"""Generate exactly {num_sections} document sections for the topic: "{topic}"
{('Additional context: ' + context) if context else ''}

Rules:
- Section 1 must be "Introduction" — set context, define the topic, explain why it matters
- Last section must be "Conclusion" — summarize key points and future outlook
- Each section body must be 4-6 FULL SENTENCES of substantive prose (not bullet lists)
- Use specific facts, dates, statistics, named examples, and real data
- Write in professional academic/report style with proper paragraph structure
- Bullets should only be used for concrete lists of items (not every section needs them)
- Do NOT start any section body by restating the heading
- Include at least 5 real data points or statistics across all sections

Output as a JSON array with {num_sections} objects, each:
{{"heading": "Section Title", "body": "Full multi-sentence paragraph...", "bullets": ["optional items"]}}

Output ONLY the JSON array, no other text."""

        raw = self._call_llm(
            prompt,
            "Expert technical writer. Output ONLY valid JSON.",
        )
        return self._parse_list(raw, "sections", num_sections, topic)

    # ── Sheet content ────────────────────────────────────────────────────────

    def generate_sheets(self, topic: str, num_sheets: int = 1,
                        context: str = "") -> List[Dict[str, Any]]:
        """Generate *num_sheets* worksheet definitions for an XLSX workbook.

        Each sheet dict has ``name``, ``headers``, and ``rows``.
        """
        prompt = f"""Generate exactly {num_sheets} spreadsheet worksheet(s) for the topic: "{topic}"
{('Additional context: ' + context) if context else ''}

Rules:
- Each sheet should have 5-8 meaningful column headers relevant to the topic
- Each sheet should have at least 8 data rows with realistic sample values
- Use concrete, varied values (not placeholder text like "value1")
- If multiple sheets, give each a distinct focus area

Output as a JSON array with {num_sheets} objects, each:
{{"name": "Sheet Name", "headers": ["Col1", "Col2", "..."], "rows": [["v1", "v2", "..."], ...]}}

Output ONLY the JSON array, no other text."""

        raw = self._call_llm(
            prompt,
            "Expert data analyst. Output ONLY valid JSON.",
        )
        return self._parse_list(raw, "sheets", num_sheets, topic)

    # ── Parser ───────────────────────────────────────────────────────────────

    def _parse_list(self, raw: str, key: str, expected: int, topic: str) -> List[Dict[str, Any]]:
        """Best-effort extraction: JSON first, then plain-text fallback."""
        import json

        # Attempt 1: Use the JSON extractor (now handles arrays too)
        try:
            from lirox.utils.llm_json import extract_json
            parsed = extract_json(raw)
            if isinstance(parsed, list) and parsed:
                return parsed
            if isinstance(parsed, dict):
                for k in (key, "items", "content", "data", "slides", "sections"):
                    if isinstance(parsed.get(k), list):
                        return parsed[k]
        except Exception:
            pass

        # Attempt 2: Direct regex for JSON array
        try:
            m = re.search(r'\[\s*\{', raw)
            if m:
                # Find the matching closing bracket
                start = m.start()
                depth = 0
                for i in range(start, len(raw)):
                    if raw[i] == '[': depth += 1
                    elif raw[i] == ']': depth -= 1
                    if depth == 0:
                        candidate = raw[start:i+1]
                        items = json.loads(candidate)
                        if isinstance(items, list) and items:
                            return items
                        break
        except Exception:
            pass

        # Attempt 3: Plain-text parser — extract structure from markdown/text
        parsed = self._parse_plain_text(raw, key, topic)
        if parsed:
            return parsed

        _logger.warning(
            "ContentGenerator._parse_list: all parsers failed for %s on topic '%s'",
            key, topic,
        )
        return self._generate_fallback(key, topic)


    def _parse_plain_text(self, raw: str, key: str, topic: str) -> List[Dict[str, Any]]:
        """Extract content from non-JSON LLM output (markdown, plain text)."""
        results = []
        lines = raw.strip().split('\n')
        current_title = ""
        current_bullets = []
        current_body = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Detect headers: "## Title", "**Title**", "Title:", "1. Title", "Slide N:"
            is_header = False
            header_text = ""

            if stripped.startswith('#'):
                header_text = stripped.lstrip('#').strip()
                is_header = True
            elif stripped.startswith('**') and stripped.endswith('**'):
                header_text = stripped.strip('*').strip()
                is_header = True
            elif re.match(r'^\d+[\.\)]\s+', stripped):
                header_text = re.sub(r'^\d+[\.\)]\s+', '', stripped).strip()
                # Only treat as header if it's short (not a full sentence)
                if len(header_text.split()) <= 8:
                    is_header = True
            elif stripped.endswith(':') and len(stripped.split()) <= 8:
                header_text = stripped.rstrip(':').strip()
                is_header = True

            if is_header and header_text:
                # Save previous section
                if current_title:
                    if key == "slides":
                        results.append({"title": current_title, "bullets": current_bullets or current_body, "notes": ""})
                    else:
                        results.append({"heading": current_title, "body": ' '.join(current_body), "bullets": current_bullets})
                current_title = header_text
                current_bullets = []
                current_body = []
                continue

            # Detect bullets: "- item", "* item", "• item"
            if re.match(r'^[-*•]\s+', stripped):
                bullet_text = re.sub(r'^[-*•]\s+', '', stripped)
                current_bullets.append(bullet_text)
            else:
                current_body.append(stripped)

        # Save last section
        if current_title:
            if key == "slides":
                results.append({"title": current_title, "bullets": current_bullets or current_body, "notes": ""})
            else:
                results.append({"heading": current_title, "body": ' '.join(current_body), "bullets": current_bullets})

        return results if len(results) >= 2 else []


    def _generate_fallback(self, key: str, topic: str) -> List[Dict[str, Any]]:
        """Last resort: ask LLM for simple plain text, then structure it."""
        try:
            # Ask for plain text — no JSON, no formatting requirements
            if key == "slides":
                raw = self._call_llm(
                    f"Write 6 short sections about '{topic}'. "
                    f"For each section write a title on its own line starting with ##, "
                    f"then 4 bullet points starting with -. Nothing else.",
                    "Write only the sections. No introduction or explanation."
                )
            else:
                raw = self._call_llm(
                    f"Write 5 short sections about '{topic}'. "
                    f"For each section write a title on its own line starting with ##, "
                    f"then a paragraph of 3 sentences. Nothing else.",
                    "Write only the sections. No introduction or explanation."
                )
            result = self._parse_plain_text(raw, key, topic)
            if result:
                return result
        except Exception:
            pass

        # Absolute last resort — static content with topic name
        if key == "slides":
            return [
                {"title": f"Introduction to {topic}", "bullets": [f"Overview of {topic}", "Historical background and context", "Why this topic matters in today's world", "Scope of this presentation"], "notes": ""},
                {"title": "Key Concepts", "bullets": ["Core principles and foundations", "Important terminology", "Fundamental mechanisms", "Theoretical framework"], "notes": ""},
                {"title": "Real-World Applications", "bullets": ["Industry use cases", "Practical implementations", "Success stories", "Emerging applications"], "notes": ""},
                {"title": "Challenges and Limitations", "bullets": ["Current technical barriers", "Ethical considerations", "Implementation difficulties", "Resource requirements"], "notes": ""},
                {"title": "Future Outlook", "bullets": ["Predicted developments", "Research directions", "Potential breakthroughs", "Long-term impact"], "notes": ""},
                {"title": "Conclusion", "bullets": [f"Key takeaways about {topic}", "Recommended actions", "Resources for learning more", "Final thoughts"], "notes": ""},
            ]
        else:
            return [
                {"heading": f"Introduction to {topic}", "body": f"{topic} represents one of the most significant developments in its field. Over recent years, it has transformed how industries operate and how people interact with technology. This document explores the key aspects, applications, and future potential of {topic}.", "bullets": []},
                {"heading": "Core Concepts and Principles", "body": f"At its foundation, {topic} relies on several interconnected principles that enable its functionality. Understanding these core concepts is essential for appreciating both the current capabilities and future potential of this field.", "bullets": []},
                {"heading": "Applications and Impact", "body": f"The practical applications of {topic} span multiple industries and domains. From healthcare and education to finance and manufacturing, organizations are finding innovative ways to leverage these capabilities for improved outcomes.", "bullets": []},
                {"heading": "Challenges and Considerations", "body": f"Despite the significant progress made in {topic}, several challenges remain. Technical limitations, ethical concerns, and implementation barriers must be addressed to enable responsible and widespread adoption.", "bullets": []},
                {"heading": "Conclusion and Future Outlook", "body": f"{topic} stands at an inflection point, with rapid advancement creating new possibilities while also raising important questions. Continued research, collaboration, and responsible development will determine how these capabilities shape the future.", "bullets": []},
            ]

    # ── Public entry point ───────────────────────────────────────────────────

    def generate(self, file_type: str, topic: str, query: str = "",
                 context: str = "") -> Dict[str, Any]:
        """Generate complete document content for *file_type*.

        Returns a dict with the appropriate content key populated:
        ``slides`` for pptx, ``sections`` for pdf/docx, ``sheets`` for xlsx.
        """
        combined_context = (query + " " + context).strip()

        if file_type == "pptx":
            slides = self.generate_slides(topic, num_slides=8, context=combined_context)
            return {"slides": slides}
        elif file_type in ("pdf", "docx"):
            sections = self.generate_sections(topic, num_sections=5, context=combined_context)
            return {"sections": sections}
        elif file_type == "xlsx":
            sheets = self.generate_sheets(topic, num_sheets=2, context=combined_context)
            return {"sheets": sheets}
        return {}

