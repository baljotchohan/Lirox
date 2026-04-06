"""Lirox v3.0 — Code Agent
Full-stack developer assistant with code reading, writing, desktop control, and bug fixes.
BUG-03, BUG-04, BUG-14 patched.
"""
from __future__ import annotations

import os
import time
import json
import re
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.config import MAX_TOOL_RESULT_CHARS, MAX_CONTEXT_CHARS, PROJECT_ROOT, ThinkingMode
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
- Desk control: take screenshots and operate UI if DESKTOP_ENABLED=true

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
  "search_web": "query to search if you need external info",
  "desktop": [{{"action": "screenshot"}}, {{"action": "open_app", "name": "Safari"}}, {{"action": "open_url", "url": "https://github.com"}}]
}}

2. Set "needs_confirmation": true for:
   - Deleting files, modifying existing files, running install commands
   - Any operation that could break things

3. Set "needs_confirmation": false for:
   - Creating new files in outputs/, reading files, ls/cat commands, screenshots

4. For questions that don't need execution, just respond normally (no JSON). If giving options for a bug fix, clearly detail Option A and Option B in standard markdown.
"""

class CodeAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "code"

    @property
    def description(self) -> str:
        return "Full-stack developer: read/write/edit files, run commands, view desktop, debug, review"

    def run(
        self, query: str, system_prompt: str = "", context: str = "", mode: str = ThinkingMode.THINK
    ) -> Generator[AgentEvent, None, None]:
        start = time.time()
        log_with_metadata(logger, "INFO", "Code Agent started", query=query[:100], mode=mode)

        cwd = os.getcwd()
        # BUG-14 FIX: Do not instantiate UserProfile locally
        agent_name = self.profile_data.get("agent_name", "Lirox")
        sys_p = CODE_SYS.format(cwd=cwd, agent_name=agent_name)

        if mode == ThinkingMode.FAST:
            sys_p += "\n\nSPEED MODE: Output minimal boilerplate, give code straight away."

        yield {"type": "agent_progress", "message": "🔍 Analyzing your request..."}

        # ── Pre-read: extract any file paths mentioned in query and inject real content
        file_contents_ctx = ""
        path_matches = re.findall(r'((?:[a-zA-Z]:[\\/]|/)[\w.\\/\-_ ]+\.(?:txt|py|html|js|css|md|json|csv|yaml|yml))', query)
        if path_matches:
            from lirox.tools.file_io import FileIOTool
            fio = FileIOTool()
            for path in path_matches:
                path = path.strip()
                if os.path.exists(path):
                    yield {"type": "tool_call", "message": f"📖 Pre-reading: {path}"}
                    try:
                        content = fio.read_file(path)
                        file_contents_ctx += f"\n\n=== FILE: {path} ===\n{content[:3000]}"
                        yield {"type": "tool_result", "message": f"✅ Read {path} ({len(content)} chars)"}
                    except Exception as e:
                        yield {"type": "tool_result", "message": f"⚠️ Could not read {path}: {e}"}

        # ── Pre-list: if query mentions a directory, list its files
        dir_matches = re.findall(r'((?:[a-zA-Z]:[\\/](?:Users|home)|/(?:Users|home))[\w.\\/\-_ ]+)', query)
        for token in query.split():
            clean_token = token.rstrip('/\\')
            is_win_abs = len(clean_token) >= 3 and clean_token[1:3] == ':\\' and clean_token[0].isalpha()
            is_unix_abs = clean_token.startswith('/')
            if (is_win_abs or is_unix_abs) and os.path.isdir(clean_token) and clean_token not in dir_matches:
                dir_matches.append(clean_token)
        for dpath in dir_matches:
            dpath = dpath.strip().rstrip('/')
            if os.path.isdir(dpath) and not file_contents_ctx:
                yield {"type": "tool_call", "message": f"📁 Listing: {dpath}"}
                try:
                    entries = os.listdir(dpath)
                    from lirox.tools.file_io import FileIOTool
                    fio = FileIOTool()
                    dir_summary = f"\n\n=== DIRECTORY: {dpath} ===\n"
                    for entry in sorted(entries):
                        full = os.path.join(dpath, entry)
                        if os.path.isfile(full) and not entry.startswith('.'):
                            dir_summary += f"  {entry} ({os.path.getsize(full)} bytes)\n"
                            if entry.endswith(('.txt', '.md', '.py', '.js', '.css', '.html')) and os.path.getsize(full) < 10000:
                                try:
                                    fc = fio.read_file(full)
                                    dir_summary += f"  --- {entry} contents ---\n{fc[:1500]}\n"
                                except Exception:
                                    pass
                    file_contents_ctx += dir_summary
                    yield {"type": "tool_result", "message": f"✅ Listed {len(entries)} items in {dpath}"}
                except Exception as e:
                    yield {"type": "tool_result", "message": f"⚠️ Could not list {dpath}: {e}"}

        # Auto-scan project if query involves code changes
        project_ctx = ""
        if any(k in query.lower() for k in [
            "fix", "debug", "review", "refactor", "analyze",
            "this file", "this project", "scan", "edit", "modify", "update"
        ]):
            yield {"type": "agent_progress", "message": "📁 Scanning project structure..."}
            project_ctx = self._scan(cwd)

        # Desktop Context
        desktop_ctx = ""
        if any(k in query.lower() for k in ["screen", "desktop", "click", "open app"]):
            from lirox.config import DESKTOP_ENABLED
            if DESKTOP_ENABLED:
                try:
                    from lirox.tools.desktop import get_open_windows
                    desktop_ctx = f"Desktop Control ENABLED. Open windows: {get_open_windows()}"
                except Exception:
                    pass

        # Build full prompt with real file contents injected
        prompt = query
        if desktop_ctx:
            prompt = f"{desktop_ctx}\n\n{prompt}"
        if file_contents_ctx:
            prompt = f"Here is the actual file content you need:\n{file_contents_ctx}\n\nTask: {prompt}"
        if project_ctx:
            prompt = f"Project Structure:\n{project_ctx}\n\n{prompt}"
        if context:
            prompt = f"Reasoning Context:\n{context}\n\n{prompt}"

        # ── Include previous memory context
        mem_ctx = self.memory.get_relevant_context(query)
        if mem_ctx:
            prompt = f"Relevant Past Context:\n{mem_ctx}\n\n{prompt}"

        yield {"type": "agent_progress", "message": "🧠 Generating solution..."}
        answer = generate_response(prompt, provider="auto", system_prompt=sys_p)

        # ── Parse Actions (JSON)
        parsed = self._parse_json_actions(answer)

        # BUG-03 fix: Keep the full answer, especially options
        options_match = re.search(r'(Option A[\s\S]+?)(\n\n|$)', answer, re.IGNORECASE)
        options_text = options_match.group(1) if options_match else ""

        if parsed:
            yield from self._execute_actions(parsed, query)
            final_answer = parsed.get("explanation", "Executed actions.")
            if options_text:
                final_answer += f"\n\n{options_text}"
            answer = final_answer
        else:
            yield from self._fallback_write_extraction(answer, query)

        self.memory.save_exchange(query, answer)

        log_with_metadata(logger, "INFO", "Code Agent completed",
                          duration_ms=int((time.time() - start) * 1000))

    def _execute_actions(self, actions: dict, query: str) -> Generator[AgentEvent, None, None]:
        """Execute parsed action plan with safety checks."""
        explanation = actions.get("explanation", "Executing...")
        plan = actions.get("plan", [])
        needs_confirm = actions.get("needs_confirmation", True)

        if plan:
            plan_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(plan))
            yield {"type": "agent_progress", "message": f"📋 Execution Plan:\n{plan_text}"}

        if needs_confirm:
            yield {"type": "agent_progress",
                   "message": f"⚠️ {explanation}\n  [Proceeding with safe operations...]"}

        # Desktop Tasks
        for desktop_action in actions.get("desktop", []):
            try:
                from lirox.tools.desktop import execute_desktop_task
                yield {"type": "tool_call", "message": f"🖥️ Desktop: {desktop_action.get('action')}"}
                res = execute_desktop_task(desktop_action)
                self.scratchpad.add_tool_result("desktop", res)
                yield {"type": "tool_result", "message": f"✅ {res}"}
            except Exception as e:
                yield {"type": "tool_result", "message": f"⚠️ Desktop action failed: {e}"}

        # Web Search
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

        # Read Files
        for path in actions.get("read_files", []):
            yield {"type": "tool_call", "message": f"📖 Reading: {path}"}
            try:
                from lirox.tools.file_io import FileIOTool
                content = FileIOTool().read_file(path)
                self.scratchpad.add_tool_result("file_read", content[:MAX_TOOL_RESULT_CHARS])
                yield {"type": "tool_result", "message": f"✅ Read {path} ({len(content)} chars)"}
            except Exception as e:
                yield {"type": "tool_result", "message": f"❌ Can't read {path}: {e}"}

        # Bash Commands
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

        # Write Files (with BUG-04 fix)
        for f in actions.get("files", []):
            path = f.get("path", "")
            content = f.get("content", "")
            if not path or not content:
                continue
            
            # BUG-04 FIX: Enforce writing within PROJECT_ROOT
            abs_path = os.path.abspath(path)
            if not abs_path.startswith(os.path.abspath(PROJECT_ROOT)):
                yield {"type": "error", "message": f"❌ Blocked Path Vulnerability: {path} is outside project root."}
                continue

            yield {"type": "tool_call", "message": f"📝 Writing: {path}"}
            try:
                from lirox.tools.file_io import FileIOTool
                res = FileIOTool().write_file(path, content)
                self.scratchpad.add_tool_result("file_write", res)
                yield {"type": "tool_result", "message": f"✅ {res}"}
            except Exception as e:
                yield {"type": "error", "message": f"❌ Write failed: {e}"}

        yield {"type": "done", "answer": f"✅ {explanation}", "sources": []}

    def _parse_json_actions(self, text: str) -> dict:
        m = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
        if m:
            try:
                r = json.loads(m.group(1))
                return r if isinstance(r, dict) else {}
            except Exception:
                pass
        m2 = re.search(r'\{[^{}]*"(?:bash|files|explanation)"[^{}]*\}', text, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group())
            except Exception:
                pass
        return {}

    def _fallback_write_extraction(self, answer: str, query: str) -> Generator[AgentEvent, None, None]:
        from lirox.tools.file_io import FileIOTool
        from lirox.tools.terminal import is_safe, run_command

        write_match = re.search(
            r'(?:write|save|create|output)\s+(?:to|at|into)?\s*((?:[a-zA-Z]:[\\/]|[/~])[\w.\\/\-_ ]+\.(?:html|py|js|css|md|txt|json|yaml))',
            query, re.IGNORECASE
        )
        path_match = re.search(
            r'(?:to|into|at)\s+((?:[a-zA-Z]:[\\/]|[/~])[\w.\\/\-_ ]+\.(?:html|py|js|css|md|txt|json|yaml))',
            query, re.IGNORECASE
        )
        target_path = write_match.group(1).strip() if write_match else (path_match.group(1).strip() if path_match else None)
        run_match = re.search(
            r'(?:run|execute|then run)\s+(python3?\s+(?:[a-zA-Z]:[\\/]|\/)[\w.\\/\-_ ]+\.py|python3?\s+[\w.\\/\-_ ]+\.py)',
            query, re.IGNORECASE
        )

        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', answer, re.DOTALL)
        if target_path and code_blocks:
            code = max(code_blocks, key=len)
            yield {"type": "tool_call", "message": f"📝 Writing extracted code → {target_path}"}
            try:
                abs_path = os.path.abspath(target_path)
                if not abs_path.startswith(os.path.abspath(PROJECT_ROOT)):
                    yield {"type": "error", "message": f"❌ Blocked Path Vulnerability: {target_path} is outside project root."}
                else:
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    res = FileIOTool().write_file(target_path, code)
                    yield {"type": "tool_result", "message": f"✅ {res}"}
            except Exception as e:
                yield {"type": "error", "message": f"❌ Write failed: {e}"}

        if run_match:
            cmd = run_match.group(1).strip()
            safe, reason = is_safe(cmd)
            if safe:
                yield {"type": "tool_call", "message": f"🔧 Running: {cmd}"}
                out = run_command(cmd)
                yield {"type": "tool_result", "message": f"Output: {out[:500]}"}
                answer = answer + f"\n\n**Execution Output:**\n```\n{out[:1000]}\n```"
            else:
                yield {"type": "error", "message": f"❌ Blocked: {reason}"}

        yield {"type": "done", "answer": answer, "sources": []}

    def _scan(self, path: str) -> str:
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
