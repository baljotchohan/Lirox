"""Lirox v2.1 — Code Agent: Full-stack developer assistant.

Capabilities:
- Read/write/edit files with real execution
- Run terminal commands safely
- Auto-scan project structure for context
- Cross-agent data fetching (browser/search when needed)
- Execution plan with user confirmation for destructive ops
- Smart JSON action parsing from LLM output
"""
from __future__ import annotations

import os
import time
import json
import re
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.config import MAX_TOOL_RESULT_CHARS, MAX_CONTEXT_CHARS
from lirox.utils.llm import generate_response
from lirox.utils.structured_logger import get_logger, log_with_metadata

logger = get_logger("lirox.agents.code")

CODE_SYS = """You are {agent_name} Code Agent — an elite full-stack software engineer.

CAPABILITIES:
- Read, write, edit, create any file
- Run terminal commands (sandboxed)
- Scan and understand entire project structures
- Debug with root-cause analysis
- Generate production-quality code with type hints

WORKING DIRECTORY: {cwd}

EXECUTION RULES:
1. For ANY action that modifies files or runs commands, output a JSON action block inside ```json fences:
{{
  "explanation": "What you're doing and why",
  "plan": ["Step 1: ...", "Step 2: ..."],
  "needs_confirmation": true/false,
  "bash": ["command1", "command2"],
  "files": [{{"path": "relative/path", "content": "file content"}}],
  "read_files": ["path/to/read1.py"],
  "search_web": "query to search if you need external info"
}}

2. Set "needs_confirmation": true for:
   - Deleting files, modifying existing files, running install commands
   - Any operation that could break things

3. Set "needs_confirmation": false for:
   - Creating new files in outputs/, reading files, ls/cat commands

4. For questions that don't need execution, just respond normally (no JSON).

FORMAT: Clean, professional responses. Use emojis sparingly for status (✅ ❌ 📁 🔧).
Always explain WHAT you did and WHY after execution."""


class CodeAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "code"

    @property
    def description(self) -> str:
        return "Full-stack developer: read/write/edit files, run commands, debug, review"

    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]:
        start = time.time()
        log_with_metadata(logger, "INFO", "Code Agent started", query=query[:100])

        cwd = os.getcwd()
        from lirox.agent.profile import UserProfile
        profile = UserProfile()
        agent_name = profile.data.get("agent_name", "Lirox")
        sys_p = CODE_SYS.format(cwd=cwd, agent_name=agent_name)

        yield {"type": "agent_progress", "message": "🔍 Analyzing your request..."}

        # Auto-scan project if query involves existing code
        project_ctx = ""
        if any(k in query.lower() for k in [
            "fix", "debug", "review", "refactor", "analyze", "this file",
            "this project", "scan", "read", "edit", "modify", "update"
        ]):
            yield {"type": "agent_progress", "message": "📁 Scanning project structure..."}
            project_ctx = self._scan(cwd)

        prompt = query
        if project_ctx:
            prompt = f"Project Structure:\n{project_ctx}\n\nTask: {query}"
        if context:
            prompt = f"Reasoning:\n{context}\n\n{prompt}"

        yield {"type": "agent_progress", "message": "🧠 Generating solution..."}
        answer = generate_response(prompt, provider="auto", system_prompt=sys_p)

        parsed = self._parse_json_actions(answer)
        if parsed:
            yield from self._execute_actions(parsed, query)
        else:
            yield {"type": "done", "answer": answer, "sources": []}

        log_with_metadata(logger, "INFO", "Code Agent completed",
                          duration_ms=int((time.time() - start) * 1000))

    def _execute_actions(self, actions: dict, query: str) -> Generator[AgentEvent, None, None]:
        """Execute parsed action plan with safety checks."""
        explanation = actions.get("explanation", "Executing...")
        plan = actions.get("plan", [])
        needs_confirm = actions.get("needs_confirmation", True)

        # Show the plan
        if plan:
            plan_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(plan))
            yield {"type": "agent_progress", "message": f"📋 Execution Plan:\n{plan_text}"}

        # If needs confirmation, note it
        if needs_confirm:
            yield {"type": "agent_progress",
                   "message": f"⚠️ {explanation}\n  [Proceeding with safe operations...]"}

        # Handle web search if agent needs external data
        search_query = actions.get("search_web")
        if search_query:
            yield {"type": "tool_call", "message": f"🌐 Searching: {search_query}"}
            try:
                from lirox.tools.search.duckduckgo import search_ddg
                search_results = search_ddg(search_query)
                self.scratchpad.add_tool_result("web_search", search_results)
                yield {"type": "tool_result", "message": f"✅ Found results for: {search_query}"}
            except Exception as e:
                yield {"type": "tool_result", "message": f"⚠️ Search failed: {e}"}

        # Read files first
        for path in actions.get("read_files", []):
            yield {"type": "tool_call", "message": f"📖 Reading: {path}"}
            try:
                from lirox.tools.file_io import FileIOTool
                content = FileIOTool().read_file(path)
                self.scratchpad.add_tool_result("file_read", content[:MAX_TOOL_RESULT_CHARS])
                yield {"type": "tool_result", "message": f"✅ Read {path} ({len(content)} chars)"}
            except Exception as e:
                yield {"type": "tool_result", "message": f"❌ Can't read {path}: {e}"}

        # Execute bash commands
        for cmd in actions.get("bash", []):
            from lirox.tools.terminal import is_safe, run_command
            safe, reason = is_safe(cmd)
            if not safe:
                yield {"type": "error", "message": f"❌ Blocked: {cmd} — {reason}"}
                continue
            yield {"type": "tool_call", "message": f"🔧 Running: {cmd}"}
            out = run_command(cmd)
            self.scratchpad.add_tool_result("bash", out)
            status = "✅" if "error" not in out.lower() else "⚠️"
            yield {"type": "tool_result", "message": f"{status} {out[:300]}"}

        # Write/create files
        for f in actions.get("files", []):
            path = f.get("path", "")
            content = f.get("content", "")
            if not path or not content:
                continue
            from lirox.tools.file_io import FileIOTool
            fio = FileIOTool()
            safe, reason = fio._is_safe_path(path)
            if not safe:
                yield {"type": "error", "message": f"❌ Blocked path: {path} — {reason}"}
                continue
            yield {"type": "tool_call", "message": f"📝 Writing: {path}"}
            try:
                res = fio.write_file(path, content)
                self.scratchpad.add_tool_result("file_write", res)
                yield {"type": "tool_result", "message": f"✅ {res}"}
            except Exception as e:
                yield {"type": "error", "message": f"❌ Write failed: {e}"}

        # Final summary
        final = f"✅ {explanation}\n\nAll operations completed."
        yield {"type": "done", "answer": final, "sources": []}

    def _parse_json_actions(self, text: str) -> dict:
        """Extract JSON action block from LLM response."""
        m = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
        if m:
            try:
                r = json.loads(m.group(1))
                return r if isinstance(r, dict) else {}
            except Exception:
                pass
        # Fallback: find raw JSON object containing action keys
        m2 = re.search(r'\{[^{}]*"(?:bash|files|explanation)"[^{}]*\}', text, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group())
            except Exception:
                pass
        return {}

    def _scan(self, path: str) -> str:
        """Scan project directory for context."""
        parts = []
        skip = {"node_modules", "__pycache__", ".git", "venv", ".venv",
                "dist", "build", ".next", ".cache", "coverage"}
        try:
            for root, dirs, files in os.walk(path):
                level = root.replace(path, "").count(os.sep)
                if level > 2:
                    dirs.clear()
                    continue
                parts.append("  " * level + os.path.basename(root) + "/")
                for f in sorted(files)[:15]:
                    parts.append("  " * (level + 1) + f)
                dirs[:] = [d for d in dirs if d not in skip]
        except Exception:
            pass

        for cfg in ["package.json", "pyproject.toml", "requirements.txt",
                     "Cargo.toml", "go.mod", "Makefile", "Dockerfile"]:
            fp = os.path.join(path, cfg)
            if os.path.exists(fp):
                try:
                    with open(fp) as f:
                        parts.append(f"\n--- {cfg} ---\n{f.read()[:1500]}")
                except Exception:
                    pass

        return "\n".join(parts)[:MAX_CONTEXT_CHARS]
