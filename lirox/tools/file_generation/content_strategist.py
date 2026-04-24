"""Content Strategist — Creates rich, audience-aware content using dynamic generation or fallbacks."""
from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional, Callable, Generator

_logger = logging.getLogger("lirox.file_generation.content_strategist")


class ContentStrategist:
    """Creates content strategically based on audience and topic."""

    @staticmethod
    def generate(topic: str, query: str, file_type: str, 
                  audience: str = "general",
                  structure_hints: List[str] = None,
                  design_context: str = "") -> Generator[Dict[str, Any], None, None]:
        """Generate rich, substantive content and yield progress events."""
        
        from lirox.tools.content_generator import ContentGenerator
        generator = ContentGenerator()
        
        sections = []
        for event in generator.generate_sections(
            topic=topic,
            num_sections=len(structure_hints) if structure_hints else 5,
            context=f"{query}\n{design_context}",
            structure_hints=structure_hints
        ):
            if event["type"] == "progress":
                yield {"type": "progress", "message": event["message"]}
            elif event["type"] == "section":
                section = event["data"]
                
                word_count = len(section.get('body', '').split())
                if word_count < 100:
                    yield {"type": "progress", "message": f"Refining Section: {section.get('heading')}..."}
                    section = ContentStrategist._regenerate_section(section, design_context)
                
                sections.append(section)

        yield {
            "type": "result",
            "data": {
                'title': topic,
                'sections': sections,
                'slides': [{'title': s.get('heading'), 'bullets': [s.get('body')[:80]], 'notes': s.get('body')} for s in sections],
                'sheets': [{'name': 'Data', 'headers': ['Heading', 'Body'], 'rows': [[s.get('heading'), s.get('body')] for s in sections]}]
            }
        }
    
    @staticmethod
    def _regenerate_section(thin_section: Dict, design_context: str) -> Dict:
        """Regenerate a section that is too thin."""
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
            system_prompt="STRICT DOCUMENT ENGINE. Generate rich, detailed content. NO filler. NO meta-commentary. NO placeholders."
        )
        
        return {
            'heading': thin_section.get('heading', 'Content'),
            'body': response,
            'bullets': [],
        }

    @staticmethod
    def _parse_sections(text: str, query: str) -> List[Dict]:
        import re
        sections = []
        lines = text.strip().split('\n')
        current_heading = ""
        current_body = []
        header_pattern = re.compile(r'^(?:#+\s+|\*\*\d*[\.\)]?\s*|\d+[\.\)]\s+)(.+?)(?:\s*\**)?:?$')

        for line in lines:
            stripped = line.strip()
            if not stripped: continue
            match = header_pattern.match(stripped)
            is_header = False
            if match:
                header_text = match.group(1).strip()
                if len(header_text.split()) <= 10:
                    is_header = True
            elif stripped.endswith(':') and len(stripped.split()) <= 8:
                header_text = stripped[:-1].strip()
                is_header = True
            
            if is_header:
                if current_heading and current_body:
                    sections.append({
                        'heading': current_heading,
                        'body': '\n'.join(current_body).strip(),
                        'bullets': []
                    })
                current_heading = header_text
                current_body = []
            else:
                current_body.append(line)
        
        if current_heading and current_body:
            sections.append({
                'heading': current_heading,
                'body': '\n'.join(current_body).strip(),
                'bullets': []
            })
        
        if not sections:
            sections.append({
                'heading': query[:60].strip() or "General Overview",
                'body': text.strip(),
                'bullets': []
            })
        return sections

    @staticmethod
    def _from_structure(topic: str, sections: List[str], file_type: str, audience: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"title": topic, "sections": [], "slides": [], "sheets": []}
        if file_type == "pptx":
            result["slides"] = [{"title": h.split("—")[0].strip() if "—" in h else h, "bullets": [f"Key aspect of {topic}", "Important facts"], "notes": ""} for h in sections]
        elif file_type == "xlsx":
            result["sheets"] = [{"name": topic[:31], "headers": ["Category", "Detail"], "rows": [[s, f"Details about {s}"] for s in sections]}]
        else:
            result["sections"] = [{"heading": h, "body": f"Overview of {h}", "bullets": []} for h in sections]
        return result

    @staticmethod
    def _generic(topic: str, file_type: str, audience: str) -> Dict[str, Any]:
        sections = [{"heading": f"Introduction to {topic}", "body": f"Overview of {topic}.", "bullets": []}]
        return {"title": topic, "sections": sections, "slides": [], "sheets": []}
