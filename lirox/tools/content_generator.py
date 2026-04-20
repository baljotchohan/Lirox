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
- Each slide must have a unique, descriptive title
- Each slide must have 4-6 bullet points
- Each bullet must be a complete sentence or detailed phrase (not just 2-3 words)
- Include concrete facts, statistics, examples where possible
- Vary the focus: intro, background, key points, case studies, benefits, challenges, future, conclusion
- Speaker notes should add context not shown on the slide

Output as a JSON array with {num_slides} objects, each:
{{"title": "...", "bullets": ["...", "...", "...", "...", "..."], "notes": "..."}}

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
- Include an introduction section and a conclusion section
- Each section body must be 3-5 full sentences of substantive prose
- Avoid repeating the section heading as the first sentence
- Include specific facts, dates, numbers, and named examples
- Bullets should be used for lists of discrete items (not required for every section)

Output as a JSON array with {num_sections} objects, each:
{{"heading": "...", "body": "Full paragraph text here...", "bullets": ["optional", "items"]}}

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
        """Best-effort JSON list extraction with fallback content."""
        try:
            from lirox.utils.llm_json import extract_json
            parsed = extract_json(raw)
            # extract_json returns a dict; unwrap if it has a list key
            if isinstance(parsed, dict):
                for k in (key, "items", "content", "data"):
                    if isinstance(parsed.get(k), list):
                        return parsed[k]
            elif isinstance(parsed, list):
                return parsed
        except Exception:
            pass

        # Fallback: try a raw JSON array parse
        try:
            import json
            # Find JSON array in the raw text
            m = re.search(r'\[[\s\S]*\]', raw)
            if m:
                items = json.loads(m.group(0))
                if isinstance(items, list):
                    return items
        except Exception:
            pass

        _logger.warning(
            "ContentGenerator._parse_list: could not parse %s from LLM for topic '%s'",
            key, topic,
        )
        return []

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
