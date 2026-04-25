"""
Step Executor
Executes plan steps and returns receipts with actual results.
"""
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("lirox.pipeline.executor")


@dataclass
class ExecutionReceipt:
    """What actually happened during execution (not what LLM claims)."""
    step_description: str
    success: bool
    error: Optional[str]
    data: Dict[str, Any]
    elapsed: float = 0.0


class StepExecutor:
    """Executes individual plan steps and returns truthful receipts."""

    # Action → handler dispatch map
    _DISPATCH = {
        "create_dir":       "_execute_create_dir",
        "generate_section": "_execute_generate_section",
        "create_document":  "_execute_create_document",
        "read_file":        "_execute_read_file",
        "write_file":       "_execute_write_file",
        "list_files":       "_execute_list_files",
        "run_shell":        "_execute_shell",
        "web_search":       "_execute_web_search",
        "generate_chat":    "_execute_chat",
    }

    def execute(self, step) -> ExecutionReceipt:
        """Execute one step. Returns ExecutionReceipt regardless of outcome."""
        start = time.time()
        handler_name = self._DISPATCH.get(step.action)

        if handler_name is None:
            return ExecutionReceipt(
                step_description=step.description,
                success=False,
                error=f"Unknown action: {step.action}",
                data={},
                elapsed=time.time() - start,
            )

        try:
            handler = getattr(self, handler_name)
            result = handler(step.params)
            return ExecutionReceipt(
                step_description=step.description,
                success=True,
                error=None,
                data=result,
                elapsed=time.time() - start,
            )
        except Exception as exc:
            _logger.error("Step '%s' failed: %s", step.description, exc, exc_info=True)
            return ExecutionReceipt(
                step_description=step.description,
                success=False,
                error=str(exc),
                data={},
                elapsed=time.time() - start,
            )

    # ── Action implementations ───────────────────────────────────────────────

    def _execute_create_dir(self, params: Dict) -> Dict:
        path = os.path.expanduser(params["path"])
        os.makedirs(path, exist_ok=True)
        return {"path": path, "created": True}

    def _execute_generate_section(self, params: Dict) -> Dict:
        """
        Generate content for ONE section.

        CRITICAL FIX: section-by-section generation prevents the
        "same paragraph 20x" repetition bug.
        """
        from lirox.designer.content_writer import ContentWriter
        from lirox.quality.content_validator import ContentValidator

        section = params["section"]
        intent = params["intent"]
        section_index = params["section_index"]
        previous = params.get("previous_sections", [])

        writer = ContentWriter()
        validator = ContentValidator()

        content = writer.write_section(
            section_name=section.name,
            section_purpose=section.purpose,
            intent=intent,
            section_index=section_index,
        )

        # Minimum length guard
        if len(content) < 200:
            raise ValueError(
                f"Section '{section.name}' content too short ({len(content)} chars)"
            )

        # Anti-repetition: regenerate if too similar to any previous section
        if previous and validator.is_repetitive(content, previous):
            _logger.info("Repetition detected in section '%s' — regenerating", section.name)
            content = writer.write_section(
                section_name=section.name,
                section_purpose=section.purpose,
                intent=intent,
                section_index=section_index,
                avoid_phrases="\n".join(previous)[:500],
            )

        # Relevance guard — warn only, never hard-fail.
        # The validator uses keyword heuristics that can produce false positives
        # (e.g. "code of conduct" in Sikh history triggers "code" marker).
        # Logging the warning is enough; the LLM prompt already constrains domain.
        if not validator.is_relevant(content, intent.domain):
            _logger.warning(
                "Relevance check flagged section '%s' for domain '%s' — "
                "keeping content (heuristic may be over-sensitive)",
                section.name, intent.domain,
            )

        return {
            "section_name": section.name,
            "content": content,
            "word_count": len(content.split()),
            "char_count": len(content),
        }

    def _execute_create_document(self, params: Dict) -> Dict:
        """
        Assemble the final document from generated sections.

        Delegates to the existing document_creators infrastructure.
        """
        file_format = params["format"]
        path = os.path.expanduser(params["path"])
        intent = params["intent"]
        structure = params["structure"]
        sections_content: List[Dict] = params.get("sections_content", [])

        os.makedirs(os.path.dirname(path), exist_ok=True)

        if file_format == "pdf":
            self._assemble_pdf(path, intent, structure, sections_content)

        elif file_format == "docx":
            self._assemble_docx(path, intent, structure, sections_content)

        elif file_format == "xlsx":
            self._assemble_xlsx(path, intent, structure, sections_content)

        elif file_format == "pptx":
            self._assemble_pptx(path, intent, structure, sections_content)

        elif file_format in ("md", "txt"):
            self._assemble_markdown(path, sections_content)

        else:
            # Fallback: plain text
            self._assemble_markdown(path, sections_content)

        # Hard verification — trust the disk, not the function
        if not os.path.exists(path):
            raise RuntimeError(f"File not created on disk: {path}")
        size = os.path.getsize(path)
        if size == 0:
            raise RuntimeError(f"File is empty (0 bytes): {path}")

        return {"path": path, "format": file_format, "size": size, "verified": True}

    def _assemble_pdf(self, path, intent, structure, sections_content):
        """Use existing PDF creator with adapted content format."""
        from lirox.tools.document_creators import create_pdf

        # Convert designer sections to the format expected by pdf_creator
        sections = [
            {
                "heading": s.get("section_name", "Section"),
                "body": s.get("content", ""),
                "bullets": [],
            }
            for s in sections_content
        ]
        title = intent.domain.title() + " Document"

        # pdf_creator returns a FileReceipt; we need the file to exist
        create_pdf(path, title, sections, query=intent.primary_purpose,
                   user_name="", user_expertise="intermediate")

    def _assemble_docx(self, path, intent, structure, sections_content):
        from lirox.tools.document_creators import create_docx

        sections = [
            {
                "heading": s.get("section_name", "Section"),
                "body": s.get("content", ""),
                "bullets": [],
            }
            for s in sections_content
        ]
        title = intent.domain.title() + " Document"
        create_docx(path, title, sections, query=intent.primary_purpose,
                    user_name="", user_expertise="intermediate")

    def _assemble_xlsx(self, path, intent, structure, sections_content):
        from lirox.tools.document_creators import create_xlsx

        sheets = [
            {
                "name": s.get("section_name", "Sheet")[:31],
                "headers": ["Content"],
                "rows": [[s.get("content", "")]],
            }
            for s in sections_content
        ]
        title = intent.domain.title() + " Spreadsheet"
        create_xlsx(path, title, sheets, query=intent.primary_purpose,
                    user_name="", user_expertise="intermediate")

    def _assemble_pptx(self, path, intent, structure, sections_content):
        from lirox.tools.document_creators import create_pptx

        slides = [
            {
                "title": s.get("section_name", "Slide"),
                "bullets": [s.get("content", "")[:200]],
                "notes": s.get("content", ""),
            }
            for s in sections_content
        ]
        title = intent.domain.title() + " Presentation"
        create_pptx(path, title, slides, query=intent.primary_purpose,
                    user_name="", user_expertise="intermediate")

    def _assemble_markdown(self, path, sections_content):
        with open(path, "w", encoding="utf-8") as fh:
            for section in sections_content:
                name = section.get("section_name", "Section")
                content = section.get("content", "")
                fh.write(f"# {name}\n\n{content}\n\n---\n\n")

    def _execute_read_file(self, params: Dict) -> Dict:
        path = os.path.expanduser(params["path"])
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        return {"path": path, "content": content[:5000], "size": len(content)}

    def _execute_write_file(self, params: Dict) -> Dict:
        from lirox.utils.llm import generate_response

        path = os.path.expanduser(params["path"])
        query = params.get("query", "")

        prompt = (
            f"Generate complete file content for this request: {query}\n\n"
            "Output ONLY the file content. No markdown fences. No explanation."
        )
        content = generate_response(prompt, provider="auto")
        content = content.replace("```", "").strip()

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

        return {"path": path, "size": len(content)}

    def _execute_list_files(self, params: Dict) -> Dict:
        directory = os.path.expanduser(params["directory"])
        if not os.path.isdir(directory):
            raise NotADirectoryError(f"Not a directory: {directory}")
        files = []
        for name in os.listdir(directory):
            full = os.path.join(directory, name)
            files.append({
                "name": name,
                "is_dir": os.path.isdir(full),
                "size": os.path.getsize(full) if os.path.isfile(full) else 0,
            })
        return {"directory": directory, "files": files, "count": len(files)}

    def _execute_shell(self, params: Dict) -> Dict:
        command = params["command"]
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _execute_web_search(self, params: Dict) -> Dict:
        from lirox.tools.search.duckduckgo import search as ddg_search
        query = params["query"]
        results = ddg_search(query, max_results=5)
        return {"query": query, "results": results, "count": len(results)}

    def _execute_chat(self, params: Dict) -> Dict:
        from lirox.utils.llm import generate_response
        from lirox.agents.personal_agent import _get_sys

        query = params["query"]
        context = params.get("context", {})
        system_prompt = _get_sys(context.get("profile_data", {}))
        response = generate_response(query, provider="auto", system_prompt=system_prompt)
        return {"query": query, "response": response}
