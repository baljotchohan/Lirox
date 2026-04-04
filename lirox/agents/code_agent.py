"""Code Agent — Claw-Code-inspired coding workflows with project scanning."""
from __future__ import annotations

import os
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.config import MAX_TOOL_RESULT_CHARS, MAX_CONTEXT_CHARS
from lirox.utils.llm import generate_response

import json
import re

CODE_SYS = """You are the Code Agent — a senior software engineer.
Write production-quality code. Type hints always. Handle errors gracefully.
Debug with root cause analysis. Review for security + performance.
Working directory: {cwd}

If you determine that you need to physically create files or run terminal commands to fulfill the user's request, you MUST output a JSON block matching this exact structure inside ```json fences:
{{
  "explanation": "Brief explanation of what you are doing",
  "bash": ["list of exact bash commands to run"],
  "files": [{{"path": "/absolute/or/relative/path", "content": "exact file content"}}]
}}
Otherwise, just respond normally."""

class CodeAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "code"

    @property
    def description(self) -> str:
        return "Code generation, writing files, terminal execution, debugging"

    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time
        logger = get_logger(f"lirox.agents.{self.name}")
        start = time.time()
        log_with_metadata(logger, "INFO", "Agent started", agent=self.name, query=query[:100])

        cwd = os.getcwd()
        sys_p = CODE_SYS.format(cwd=cwd)
        yield {"type": "agent_progress", "message": "Code Agent analyzing..."}

        project_ctx = ""
        if any(
            k in query.lower()
            for k in ["fix", "debug", "review", "refactor", "analyze", "this file"]
        ):
            yield {"type": "agent_progress", "message": "Scanning project..."}
            project_ctx = self._scan(cwd)

        prompt = query
        if project_ctx:
            prompt = f"Project:\n{project_ctx}\n\nTask: {query}"
        if context:
            prompt = f"Thinking:\n{context}\n\n{prompt}"

        yield {"type": "agent_progress", "message": "Generating solution..."}
        answer = generate_response(prompt, provider="auto", system_prompt=sys_p)
        
        parsed_actions = self._parse_json_actions(answer)
        if parsed_actions:
            explanation = parsed_actions.get("explanation", "Executing requested actions...")
            yield {"type": "agent_progress", "message": explanation}
            
            # Execute bash commands WITH SAFETY VALIDATION
            bash_cmds = parsed_actions.get("bash", [])
            for cmd in bash_cmds:
                # Validate command through terminal safety before execution
                from lirox.tools.terminal import is_safe
                safe, reason = is_safe(cmd)
                if not safe:
                    yield {"type": "error", "message": f"Blocked unsafe command: {cmd} — {reason}"}
                    continue
                yield {"type": "tool_call", "message": f"Running: {cmd}"}
                from lirox.tools.terminal import run_command
                out = run_command(cmd)
                self.scratchpad.add_tool_result("bash", out)
                yield {"type": "tool_result", "message": f"Output: {out[:200]}"}

            # Write files WITH PATH VALIDATION
            files = parsed_actions.get("files", [])
            for f in files:
                path = f.get("path")
                content = f.get("content")
                if path and content:
                    from lirox.tools.file_io import FileIOTool
                    fio = FileIOTool()
                    safe, reason = fio._is_safe_path(path)
                    if not safe:
                        yield {"type": "error", "message": f"Blocked unsafe path: {path} — {reason}"}
                        continue
                    yield {"type": "tool_call", "message": f"Writing: {path}"}
                    res = fio.write_file(path, content)
                    self.scratchpad.add_tool_result("file_write", res)
                    yield {"type": "tool_result", "message": f"Saved: {path}"}
            
            final_answer = explanation + "\n\nAll requested operations completed."
            yield {"type": "done", "answer": final_answer, "sources": []}
        else:
            yield {"type": "done", "answer": answer, "sources": []}

    def _parse_json_actions(self, text: str) -> dict:
        m = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
        if m:
            text = m.group(1)
        try:
            r = json.loads(text)
            return r if isinstance(r, dict) else {}
        except Exception:
            # try to find a raw json object
            m2 = re.search(r"\{.*\}", text, re.DOTALL)
            if m2:
                try:
                    return json.loads(m2.group())
                except Exception:
                    pass
        return {}

    def _scan(self, path: str) -> str:
        parts = []
        skip = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"}
        try:
            for root, dirs, files in os.walk(path):
                level = root.replace(path, "").count(os.sep)
                if level > 2:
                    continue
                parts.append("  " * level + os.path.basename(root) + "/")
                for f in sorted(files)[:15]:
                    parts.append("  " * (level + 1) + f)
                dirs[:] = [d for d in dirs if d not in skip]
        except Exception:
            pass

        for cfg in [
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "Cargo.toml",
            "go.mod",
            "Makefile",
        ]:
            fp = os.path.join(path, cfg)
            if os.path.exists(fp):
                try:
                    with open(fp) as f:
                        parts.append(f"\n--- {cfg} ---\n{f.read()[:MAX_TOOL_RESULT_CHARS]}")
                except Exception as e:
                    logger.warning(f"Non-critical error reading config {cfg}: {e}")

        log_with_metadata(logger, "INFO", "Agent completed", agent=self.name, duration_ms=int((time.time()-start)*1000))
        return "\n".join(parts)[:MAX_CONTEXT_CHARS]
