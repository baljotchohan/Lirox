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
        
        # Lirox v1.2 Strict Document Engine Protocol
        strict_sys = (
            "SYSTEM ROLE: You are a strict document generation engine. Your ONLY function is to produce clean, final-form documents. "
            "You are NOT a teacher, NOT an explainer, and NOT a conversational assistant.\n\n"
            "GLOBAL HARD RULES:\n"
            "- Do NOT explain anything\n"
            "- Do NOT describe what you are doing\n"
            "- Do NOT include meta commentary or reasoning\n"
            "- Do NOT include phrases like 'this section', 'this document', 'in this part'\n"
            "- Do NOT include educational or historical content unless explicitly requested\n"
            "- Do NOT generate placeholder or dummy content (e.g., 'John Doe', 'example@email.com')\n"
            "- Do NOT hallucinate fake tools, companies, platforms, or facts\n"
            "- Do NOT repeat content or rephrase the same idea multiple times\n\n"
            "OUTPUT QUALITY:\n"
            "- Output must look like it was written by a professional human\n"
            "- Output must be concise, structured, and purpose-driven\n"
            "- Use formatting appropriate to the document type\n"
            "- Every line must add value (no filler content)"
        )
        
        return generate_response(
            prompt, provider="auto",
            system_prompt=system_prompt or strict_sys,
        )

    # ── Slide content ────────────────────────────────────────────────────────

    def generate_slides(self, topic: str, num_slides: int = 8,
                        context: str = "", structure_hints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Generate *num_slides* content slides for a PPTX presentation dynamically.

        Each slide dict has ``title``, ``bullets`` (3-6 items), and
        ``notes`` (speaker notes).
        """
        
        hints_text = ""
        if structure_hints:
            hints_text = f"\nYou MUST use exactly these slide titles:\n" + "\n".join([f"- {h}" for h in structure_hints]) + "\n"

        prompt = f"""Design a dynamic presentation structure for the topic: "{topic}"
{('Additional context: ' + context) if context else ''}{hints_text}

Rules:
- Adapt the number of slides and their progression entirely based on what is most appropriate for this specific topic (e.g., around {num_slides} slides, but plan whatever is best).
- Do NOT use a fixed template.
- Each slide must have a UNIQUE, specific, descriptive title.
- Each slide must have 3-6 DETAILED bullet points (complete sentences with specific facts, numbers, or examples).
- Include real statistics or data points across the slides.
- Speaker notes should add 2-3 sentences of context not shown on the slide.

Output as a JSON array of objects, where each object represents a slide:
{{"title": "Specific Descriptive Title", "bullets": ["Detailed point with specific fact...", "Another detailed point..."], "notes": "Speaker note with extra context..."}}

Output ONLY the JSON array, no other text."""

        raw = self._call_llm(
            prompt,
            "Expert presentation designer. Output ONLY valid JSON.",
        )
        return self._parse_list(raw, "slides", num_slides, topic, structure_hints)

    # ── Section content ──────────────────────────────────────────────────────

    def generate_sections(self, topic: str, num_sections: int = 5,
                          context: str = "", structure_hints: Optional[List[str]] = None) -> Generator[Dict[str, Any], None, None]:
        """Generate *num_sections* content sections iteratively.
        Yields each section as it is completed.
        """
        if not structure_hints:
            yield {"type": "progress", "message": "Planning document structure..."}
            structure_hints = self._generate_structure(topic, num_sections, context)
            
        for i, heading in enumerate(structure_hints):
            yield {"type": "progress", "message": f"Generating Section {i+1}/{len(structure_hints)}: {heading}..."}
            section = self._generate_single_section(topic, heading, i+1, len(structure_hints), context)
            yield {"type": "section", "data": section}



    def _generate_structure(self, topic: str, num: int, context: str) -> List[str]:
        prompt = f"Topic: {topic}\nContext: {context}\nGenerate {num} logical, high-impact section headings for a deep-dive report. Output ONLY a JSON list of strings."
        raw = self._call_llm(prompt, "Content Architect. Output ONLY JSON array.")
        from lirox.utils.llm_json import try_extract_json
        res = try_extract_json(raw)
        if isinstance(res, list): return res
        return [f"Chapter {i+1}" for i in range(num)]

    def _generate_single_section(self, topic: str, heading: str, index: int, total: int, context: str) -> Dict[str, Any]:
        prompt = f"""Generate a DEEP DIVE section for: "{topic}"
Section {index}/{total}: "{heading}"
Context: {context}

QUALITY RULES:
1. WORD COUNT: MINIMUM 400 words.
2. DEPTH: Provide historical, technical, or specific details. Use real names, dates, and facts.
3. STRUCTURE: 3-5 rich paragraphs.
4. BULLETS: Include 3-5 specific bullet points at the end for takeaways.

Output as JSON:
{{"heading": "{heading}", "body": "...", "bullets": ["..."]}}"""

        raw = self._call_llm(prompt, "STRICT DOCUMENT ENGINE. Output ONLY JSON. No explanation. No markers.")
        from lirox.utils.llm_json import try_extract_json
        res = try_extract_json(raw)
        if isinstance(res, dict) and "body" in res:
            return res
        # Fallback if JSON fails
        return {"heading": heading, "body": raw, "bullets": []}



    # ── Sheet content ────────────────────────────────────────────────────────

    def generate_sheets(self, topic: str, num_sheets: int = 1,
                        context: str = "", structure_hints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Generate *num_sheets* worksheet definitions for an XLSX workbook dynamically.

        Each sheet dict has ``name``, ``headers``, and ``rows``.
        """
        
        hints_text = ""
        if structure_hints:
            hints_text = f"\nYou MUST use exactly these sheet names:\n" + "\n".join([f"- {h}" for h in structure_hints]) + "\n"
            
        prompt = f"""Design a dynamic spreadsheet structure for the topic: "{topic}"
{('Additional context: ' + context) if context else ''}{hints_text}

Rules:
- Adapt the number of sheets, column headers, and rows entirely based on what is most appropriate for this specific topic (e.g., around {num_sheets} sheets, but use what fits).
- Do NOT use a fixed template. Create as many sheets as necessary to organize the data logically.
- Each sheet should have meaningful column headers relevant to its focus.
- Each sheet should have realistic sample data rows (at least 5-10 rows).
- Use concrete, varied values (not placeholder text like "value1").

Output as a JSON array of objects, where each object represents a sheet:
{{"name": "Sheet Name", "headers": ["Col1", "Col2", "..."], "rows": [["v1", "v2", "..."], ...]}}

Output ONLY the JSON array, no other text."""

        raw = self._call_llm(
            prompt,
            "Expert data analyst. Output ONLY valid JSON.",
        )
        return self._parse_list(raw, "sheets", num_sheets, topic, structure_hints)

    # ── Parser ───────────────────────────────────────────────────────────────

    def _parse_list(self, raw: str, key: str, expected: int, topic: str, structure_hints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
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

        # Attempt 2: Direct regex for JSON array or single object
        try:
            import json
            # Check for array
            m_array = re.search(r'\[\s*\{', raw)
            if m_array:
                start = m_array.start()
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
            
            # Check for single object
            m_obj = re.search(r'\{\s*"(heading|title|name)"', raw)
            if m_obj:
                start = m_obj.start()
                depth = 0
                for i in range(start, len(raw)):
                    if raw[i] == '{': depth += 1
                    elif raw[i] == '}': depth -= 1
                    if depth == 0:
                        candidate = raw[start:i+1]
                        item = json.loads(candidate)
                        if isinstance(item, dict):
                            return [item]
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
        return self._generate_fallback(key, topic, structure_hints)


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


    def _generate_fallback(self, key: str, topic: str, structure_hints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
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
        # Absolute last resort — use structure hints if provided
        if structure_hints:
            results = []
            for h in structure_hints:
                if key == "slides":
                    results.append({"title": h, "bullets": [f"Key point about {h}", "Detailed discussion", "Examples and applications"], "notes": ""})
                else:
                    results.append({"heading": h, "body": f"Detailed content covering {h}. This section explores the key aspects, applications, and core principles related to this topic.", "bullets": []})
            return results

        # Ultimate absolute last resort — static content with topic name
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
                 context: str = "", structure_hints: Optional[List[str]] = None,
                 section_count: int = 0) -> Dict[str, Any]:
        """Generate complete document content for *file_type*.

        Returns a dict with the appropriate content key populated:
        ``slides`` for pptx, ``sections`` for pdf/docx, ``sheets`` for xlsx.
        Always includes all three keys so callers can safely access any.
        """
        combined_context = (query + " " + context).strip()

        # Ensure result dict always has all keys (v1.1 fix)
        result: Dict[str, Any] = {
            "file_type": file_type,
            "title": topic or "Untitled",
            "sections": [],
            "slides": [],
            "sheets": [],
        }

        try:
            if file_type == "pptx":
                result["slides"] = self.generate_slides(topic, num_slides=section_count or 8, context=combined_context, structure_hints=structure_hints) or []
            elif file_type in ("pdf", "docx"):
                result["sections"] = self.generate_sections(topic, num_sections=section_count or 5, context=combined_context, structure_hints=structure_hints) or []
            elif file_type == "xlsx":
                result["sheets"] = self.generate_sheets(topic, num_sheets=2, context=combined_context) or []
        except Exception as e:
            _logger.warning("ContentGenerator.generate failed: %s", e)

        # ENSURE all three keys exist before returning (v1.1 critical fix)
        result.setdefault("sections", [])
        result.setdefault("slides", [])
        result.setdefault("sheets", [])

        return result

