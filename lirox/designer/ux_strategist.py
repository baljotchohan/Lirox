"""
UX Strategist
Designs document/website structure from intent and domain patterns.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import List

from lirox.designer.domain_knowledge import DomainKnowledge
from lirox.utils.llm import generate_response

_logger = logging.getLogger("lirox.designer.ux")


@dataclass
class Section:
    """One content section."""
    name: str
    purpose: str          # what this section accomplishes
    content_type: str     # "text", "list", "table", "chart", "title"
    cta: str              # call-to-action (empty for documents)


@dataclass
class SiteStructure:
    """Complete structural plan for a document or site."""
    sections: List[Section]
    user_journey: List[str]
    trust_elements: List[str]


class UXStrategist:
    """Maps intent + format → logical information architecture."""

    def design_structure(self, intent, file_format: str) -> SiteStructure:
        if file_format in ("html", "website"):
            return self._design_website(intent)
        elif file_format in ("pdf", "docx", "md", "txt"):
            return self._design_document(intent)
        elif file_format == "xlsx":
            return self._design_spreadsheet(intent)
        elif file_format == "pptx":
            return self._design_presentation(intent)
        return self._design_document(intent)

    # ── Website ──────────────────────────────────────────────────────────────

    def _design_website(self, intent) -> SiteStructure:
        pattern = DomainKnowledge.get_pattern(intent.domain)
        section_names = pattern.get("essential_sections", ["hero", "about", "features", "contact"])

        sections = []
        for i, name in enumerate(section_names):
            if name == "hero":
                purpose = f"Grab attention and communicate value for {intent.domain}"
                cta = intent.key_actions[0] if intent.key_actions else "Learn More"
            elif name in ("pricing", "membership"):
                purpose = "Present pricing options clearly"
                cta = "Choose Plan"
            elif name == "contact":
                purpose = "Make it easy to get in touch"
                cta = "Contact Us"
            else:
                purpose = f"Showcase {name.replace('_', ' ')} for {intent.target_audience}"
                cta = intent.key_actions[1] if len(intent.key_actions) > 1 else "Learn More"

            sections.append(Section(
                name=name.replace("_", " ").title(),
                purpose=purpose,
                content_type="mixed",
                cta=cta,
            ))

        return SiteStructure(
            sections=sections,
            user_journey=pattern.get("user_journey", ["discover", "engage", "convert"]),
            trust_elements=pattern.get("trust_signals", ["testimonials"]),
        )

    # ── Document (PDF / DOCX / MD) ────────────────────────────────────────────

    def _design_document(self, intent) -> SiteStructure:
        """LLM-driven structure so every domain gets appropriate sections."""
        prompt = f"""\
Design a logical structure for a document about: {intent.domain}

Purpose: {intent.primary_purpose}
Audience: {intent.target_audience}
Tone: {intent.emotional_tone}

Create 5-7 sections. Each needs:
- "name": 2-4 word heading
- "purpose": one sentence on what it accomplishes

Return a JSON array only:
[
  {{"name": "...", "purpose": "..."}},
  ...
]
"""
        try:
            raw = generate_response(
                prompt, provider="auto",
                system_prompt="You are a UX strategist. Output JSON array only."
            )
            raw = raw.replace("```json", "").replace("```", "").strip()
            items = json.loads(raw)

            sections = [
                Section(
                    name=s["name"],
                    purpose=s["purpose"],
                    content_type="text",
                    cta="",
                )
                for s in items
                if isinstance(s, dict) and "name" in s
            ]
            if sections:
                return SiteStructure(
                    sections=sections,
                    user_journey=["read", "understand", "apply"],
                    trust_elements=["facts", "sources", "data"],
                )
        except Exception as exc:
            _logger.warning("LLM structure generation failed (%s) — using fallback", exc)

        # Hard fallback
        return SiteStructure(
            sections=[
                Section("Introduction",  f"Introduce {intent.domain}", "text", ""),
                Section("Background",    "Provide historical and contextual background", "text", ""),
                Section("Core Concepts", f"Key ideas in {intent.domain}", "text", ""),
                Section("Analysis",      "Deeper examination of key points", "text", ""),
                Section("Conclusion",    "Summarise main takeaways", "text", ""),
            ],
            user_journey=["read", "understand", "apply"],
            trust_elements=["citations", "data", "expert sources"],
        )

    # ── Spreadsheet ──────────────────────────────────────────────────────────

    def _design_spreadsheet(self, intent) -> SiteStructure:
        return SiteStructure(
            sections=[
                Section("Summary",    "Overview and key metrics", "table", ""),
                Section("Data",       "Detailed data table",      "table", ""),
                Section("Charts",     "Visual representations",   "chart", ""),
            ],
            user_journey=["analyze", "filter", "export"],
            trust_elements=["formulas", "validation"],
        )

    # ── Presentation ─────────────────────────────────────────────────────────

    def _design_presentation(self, intent) -> SiteStructure:
        return SiteStructure(
            sections=[
                Section("Title Slide",  f"Introduction to {intent.domain}", "title",   ""),
                Section("The Problem",  "Define the challenge or opportunity",  "bullets", ""),
                Section("Our Solution", "Present the approach",                 "bullets", ""),
                Section("Evidence",     "Support with data or examples",        "chart",   ""),
                Section("Next Steps",   "Summarise and call to action",         "text",    ""),
            ],
            user_journey=["engage", "understand", "decide"],
            trust_elements=["data", "visuals", "clarity"],
        )
