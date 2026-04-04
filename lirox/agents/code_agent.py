"""Code Agent — Claw-Code-inspired coding workflows with project scanning."""
from __future__ import annotations

import os
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response

CODE_SYS = """You are the Code Agent — a senior software engineer.
Write production-quality code. Type hints always. Handle errors gracefully.
Debug with root cause analysis. Review for security + performance.
Working directory: {cwd}"""


class CodeAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "code"

    @property
    def description(self) -> str:
        return "Code generation, debugging, review, project analysis"

    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]:
        cwd = os.getcwd()
        sys_p = CODE_SYS.format(cwd=cwd)
        yield {"type": "agent_start", "message": "Code Agent analyzing..."}

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
        yield {"type": "done", "answer": answer, "sources": []}

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
                        parts.append(f"\n--- {cfg} ---\n{f.read()[:1500]}")
                except Exception:
                    pass

        return "\n".join(parts)[:4000]
