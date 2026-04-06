"""
Lirox — Code Agent
11-stage autonomous developer pipeline. Each stage = dedicated LLM sub-agent.
BUG-08 FIX: Path traversal check uses Path.is_relative_to() (Python 3.9+)
"""
from __future__ import annotations

import os
import time
import json
import re
from pathlib import Path
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.config import MAX_TOOL_RESULT_CHARS, MAX_CONTEXT_CHARS, PROJECT_ROOT
from lirox.utils.llm import generate_response
from lirox.utils.structured_logger import get_logger, log_with_metadata

logger = get_logger("lirox.agents.code")

AGENT_IDENTITY = """
═══════════════════════════════════════════
  YOU ARE: {agent_name} Code Agent
  IDENTITY: Elite full-stack software engineer
  NEVER pretend to be another agent.
  NEVER route tasks to other agents in your response.
═══════════════════════════════════════════
"""

# ─── Stage System Prompts ──────────────────────────────────────────────────────

STAGE_PROMPTS = {
    "intent": """You are the Intent Analyst sub-agent of a coding pipeline.
Your ONLY job: determine exactly what the user wants to build/fix/change.
Output a JSON object:
{
  "primary_goal": "...",
  "user_skill_level": "beginner|intermediate|expert",
  "project_type": "script|web_app|api|library|cli|automation|fix",
  "scope": "small|medium|large",
  "constraints": ["language", "framework", "platform"]
}
Output ONLY valid JSON, no other text.""",

    "concept": """You are the Concept Analyzer sub-agent.
Given the intent, identify ALL technical concepts needed.
Output JSON: {"concepts": [...], "dependencies": [...], "architecture": "..."}
Output ONLY valid JSON.""",

    "plan": """You are the Project Planner sub-agent.
Create a detailed execution plan with file structure.
Output JSON: {"files": [{"path": "...", "purpose": "...", "functions": [...]}], "order": [...]}
Output ONLY valid JSON.""",

    "tasks": """You are the Task Creator sub-agent.
Convert the plan into atomic implementation tasks ordered by dependency.
Output JSON: {"tasks": [{"id": 1, "file": "...", "description": "...", "code_target": "..."}]}
Output ONLY valid JSON.""",

    "writer": """You are the Code Writer sub-agent — an elite software engineer.
Write COMPLETE, production-quality code for all files.
Rules:
- Full implementations, no placeholders or TODOs
- Type hints everywhere in Python
- Docstrings for all public functions
- Error handling with specific exceptions
- Follow PEP 8 / language conventions
Output ONLY the complete code files in ```filename\n...\n``` blocks.""",

    "tester": """You are the Test Engineer sub-agent.
Write comprehensive test cases for the code:
- Unit tests for every function
- Edge cases and error conditions
- Integration tests if applicable
Use pytest for Python. Output complete test file(s) in code blocks.""",

    "verifier": """You are the Code Verifier sub-agent.
Check the written code for:
1. Logic errors
2. Off-by-one errors
3. Null/None handling
4. Incorrect algorithm implementation
5. Missing return values
Output JSON: {"issues": [...], "verdict": "PASS|FAIL", "corrections": {}}""",

    "files": """You are the File Structure Verifier sub-agent.
Check:
1. All imports are correct and available
2. File paths in code match the plan
3. No circular imports
4. __init__.py files present where needed
5. Config/env references are correct
Output JSON: {"file_issues": [...], "import_issues": [...], "verdict": "PASS|FAIL"}""",

    "security": """You are the Security Auditor sub-agent.
Scan for:
1. SQL injection risks
2. Command injection (subprocess with user input)
3. Path traversal
4. Hardcoded credentials or secrets
5. Insecure random number usage
6. Missing input validation
7. Open redirect vulnerabilities
Output JSON: {"vulnerabilities": [...], "severity": "LOW|MEDIUM|HIGH|CRITICAL", "fixes": {}}""",

    "debugger": """You are the Debugger sub-agent.
Review the code and identify:
1. Runtime errors that would occur
2. Missing exception handlers
3. Resource leaks (unclosed files, connections)
4. Race conditions in async code
5. Memory issues
Output JSON: {"bugs": [...], "fixed_code": {}}""",

    "final": """You are the Build Master sub-agent.
Given all previous analysis, produce the FINAL clean code.
Apply all security fixes, bug fixes, and verifier corrections.
This is the DEFINITIVE version that will be written to disk.
Output complete files in ```path/to/file.py\n...\n``` blocks.
Also output: installation instructions, usage examples, any warnings.""",
}

# ─── Stage Metadata ────────────────────────────────────────────────────────────

STAGES = [
    ("intent",   "🎯 Intent Analyst",   "Understanding what you need..."),
    ("concept",  "🧩 Concept Analyzer", "Analyzing technical concepts..."),
    ("plan",     "📋 Project Planner",  "Creating execution plan..."),
    ("tasks",    "📌 Task Creator",     "Breaking into atomic tasks..."),
    ("writer",   "✍️  Code Writer",      "Writing production code..."),
    ("tester",   "🧪 Test Engineer",    "Writing test cases..."),
    ("verifier", "✅ Code Verifier",    "Verifying correctness..."),
    ("files",    "📁 File Verifier",    "Checking file structure..."),
    ("security", "🔒 Security Auditor", "Scanning for vulnerabilities..."),
    ("debugger", "🐛 Debugger",        "Checking for bugs..."),
    ("final",    "🚀 Build Master",    "Finalizing solution..."),
]

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
  "search_web": "query to search if you need external info",
  "desktop": [{{"action": "screenshot"}}, {{"action": "launch", "app": "Safari"}}]
}}

2. Set "needs_confirmation": true for deleting/modifying existing files, install commands.
3. Set "needs_confirmation": false for creating new files, reading, ls/cat, screenshots.
4. For questions that don't need execution, respond normally (no JSON).
"""


class CodeAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "code"

    @property
    def description(self) -> str:
        return "Full-stack developer: 11-stage autonomous pipeline, read/write/debug/execute"

    def run(
        self, query: str, system_prompt: str = "", context: str = "", mode: str = "complex"
    ) -> Generator[AgentEvent, None, None]:
        start = time.time()
        log_with_metadata(logger, "INFO", "Code Agent started", query=query[:100])

        cwd        = os.getcwd()
        agent_name = self.profile_data.get("agent_name", "Lirox")

        # Check if this is a desktop task
        if any(k in query.lower() for k in ["open ", "click ", "on my screen", "use my computer",
                                              "navigate to", "desktop control"]):
            from lirox.config import DESKTOP_ENABLED
            if DESKTOP_ENABLED:
                yield {"type": "agent_progress", "message": "🟡 Desktop control activated — activating vision loop"}
                try:
                    from lirox.tools.desktop import DesktopController
                    controller = DesktopController()
                    controller.start()
                    yield from controller.execute_task(query)
                    controller.stop()
                except Exception as e:
                    yield {"type": "error", "message": f"Desktop control error: {e}"}
                return

        # Determine if this is a complex build task (warrants 11-stage pipeline)
        is_build_task = any(k in query.lower() for k in [
            "build", "create", "write a", "make a", "develop", "implement",
            "code", "script", "app", "api", "function", "class", "refactor"
        ])

        if is_build_task:
            yield from self._run_pipeline(query, context, cwd, agent_name)
        else:
            yield from self._run_direct(query, context, cwd, agent_name, system_prompt)

        log_with_metadata(logger, "INFO", "Code Agent completed",
                          duration_ms=int((time.time() - start) * 1000))

    # ── 11-Stage Pipeline ────────────────────────────────────────────────────

    def _run_pipeline(
        self, query: str, context: str, cwd: str, agent_name: str
    ) -> Generator[AgentEvent, None, None]:
        """Full 11-stage autonomous developer pipeline."""
        accumulated: dict = {}

        identity = AGENT_IDENTITY.format(agent_name=agent_name)

        for stage_id, stage_name, stage_msg in STAGES:
            yield {"type": "agent_progress", "message": f"{stage_name}: {stage_msg}"}

            # Build prompt with accumulated context from prior stages
            prior_ctx = ""
            if accumulated:
                prior_ctx = f"\n\nPrior stages output:\n{json.dumps(accumulated, indent=2, default=str)[:3000]}"

            prompt = f"Original request: {query}{prior_ctx}"
            if context:
                prompt += f"\n\nThinking context: {context[:500]}"

            result = generate_response(
                prompt,
                provider="auto",
                system_prompt=identity + "\n\n" + STAGE_PROMPTS[stage_id],
            )
            accumulated[stage_id] = result

            # Show brief snippet (not full output to keep terminal clean)
            preview = result[:150].replace("\n", " ")
            yield {"type": "tool_result", "message": f"  └─ {stage_name}: {preview}..."}

        # Final stage: extract and write files
        final_output = accumulated.get("final", "")
        yield from self._write_final_files(final_output, query)
        yield {"type": "done", "answer": final_output, "sources": []}

    def _write_final_files(self, final_output: str, query: str) -> Generator[AgentEvent, None, None]:
        """Extract files from Build Master output and write them to disk."""
        code_blocks = re.findall(
            r'```(?P<lang>[\w./\\-]+)\n(?P<code>.*?)\n```',
            final_output, re.DOTALL
        )
        if not code_blocks:
            return

        from lirox.tools.file_io import FileIOTool
        fio = FileIOTool()

        for lang_or_path, code in code_blocks:
            # Determine if this looks like a file path
            if "/" in lang_or_path or "." in lang_or_path:
                target_path = lang_or_path.strip()
            else:
                continue  # just a language tag, not a file path

            # BUG-08 FIX: Use Path.is_relative_to() (Python 3.9+) for safe path check
            try:
                abs_path = Path(os.path.abspath(target_path))
                project_root = Path(os.path.abspath(PROJECT_ROOT))
                if not abs_path.is_relative_to(project_root):
                    yield {"type": "error",
                           "message": f"❌ Path traversal blocked: {target_path} is outside project root"}
                    continue
            except Exception as e:
                yield {"type": "error", "message": f"❌ Path validation error: {e}"}
                continue

            yield {"type": "tool_call", "message": f"📝 Writing: {target_path}"}
            try:
                os.makedirs(abs_path.parent, exist_ok=True)
                res = fio.write_file(target_path, code)
                yield {"type": "tool_result", "message": f"✅ {res}"}
            except Exception as e:
                yield {"type": "error", "message": f"❌ Write failed: {e}"}

    # ── Direct Execution (non-build) ─────────────────────────────────────────

    def _run_direct(
        self, query: str, context: str, cwd: str, agent_name: str, system_prompt: str
    ) -> Generator[AgentEvent, None, None]:
        """Direct LLM call for smaller tasks (fixes, questions, reviews)."""
        sys_p = CODE_SYS.format(cwd=cwd, agent_name=agent_name)

        yield {"type": "agent_progress", "message": "🔍 Analyzing your request..."}

        # Pre-read files mentioned in query
        file_contents_ctx = ""
        path_matches = re.findall(
            r'((?:[a-zA-Z]:[\\/]|/)?[\w./\\-]+\.(?:txt|py|html|js|css|md|json|csv|yaml|yml))',
            query
        )
        for path in path_matches[:3]:
            path = path.strip()
            if os.path.exists(path):
                yield {"type": "tool_call", "message": f"📖 Pre-reading: {path}"}
                try:
                    from lirox.tools.file_io import FileIOTool
                    content = FileIOTool().read_file(path)
                    file_contents_ctx += f"\n\n=== FILE: {path} ===\n{content[:3000]}"
                    yield {"type": "tool_result", "message": f"✅ Read {path}"}
                except Exception as e:
                    yield {"type": "tool_result", "message": f"⚠️ Could not read {path}: {e}"}

        # Auto-scan project for review/debug tasks
        project_ctx = ""
        if any(k in query.lower() for k in ["fix", "debug", "review", "refactor", "analyze"]):
            yield {"type": "agent_progress", "message": "📁 Scanning project structure..."}
            project_ctx = self._scan(cwd)

        # Assemble prompt
        prompt = query
        if file_contents_ctx:
            prompt = f"File contents:\n{file_contents_ctx}\n\nTask: {prompt}"
        if project_ctx:
            prompt = f"Project Structure:\n{project_ctx}\n\n{prompt}"
        if context:
            prompt = f"Reasoning Context:\n{context}\n\n{prompt}"

        mem_ctx = self.memory.get_relevant_context(query)
        if mem_ctx:
            prompt = f"Past Context:\n{mem_ctx}\n\n{prompt}"

        yield {"type": "agent_progress", "message": "🧠 Generating solution..."}
        answer = generate_response(prompt, provider="auto", system_prompt=sys_p)

        parsed = self._parse_json_actions(answer)
        if parsed:
            yield from self._execute_actions(parsed, query)
            answer = parsed.get("explanation", "Executed actions.")
        else:
            yield from self._fallback_write_extraction(answer, query)

        self.memory.save_exchange(query, answer)

    def _execute_actions(self, actions: dict, query: str) -> Generator[AgentEvent, None, None]:
        explanation  = actions.get("explanation", "Executing...")
        plan         = actions.get("plan", [])
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
                yield {"type": "tool_result", "message": f"✅ Found results"}
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

        # Write Files — BUG-08 FIX: Use Path.is_relative_to()
        for f in actions.get("files", []):
            path    = f.get("path", "")
            content = f.get("content", "")
            if not path or not content:
                continue

            try:
                abs_path     = Path(os.path.abspath(path))
                project_root = Path(os.path.abspath(PROJECT_ROOT))
                if not abs_path.is_relative_to(project_root):
                    yield {"type": "error",
                           "message": f"❌ Path traversal blocked: {path} is outside project root"}
                    continue
            except Exception as e:
                yield {"type": "error", "message": f"❌ Path validation error: {e}"}
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
        """Fallback: extract code blocks and write to path if mentioned in query."""
        from lirox.tools.file_io import FileIOTool
        from lirox.tools.terminal import is_safe, run_command

        write_match = re.search(
            r'(?:write|save|create|output)\s+(?:to|at|into)?\s*((?:[a-zA-Z]:[\\/]|[/~])[\w./\\-_]+\.(?:html|py|js|css|md|txt|json|yaml))',
            query, re.IGNORECASE
        )
        path_match = re.search(
            r'(?:to|into|at)\s+((?:[a-zA-Z]:[\\/]|[/~])[\w./\\-_]+\.(?:html|py|js|css|md|txt|json|yaml))',
            query, re.IGNORECASE
        )
        target_path = (write_match.group(1).strip() if write_match
                       else path_match.group(1).strip() if path_match else None)

        run_match = re.search(
            r'(?:run|execute|then run)\s+(python3?\s+(?:[a-zA-Z]:[\\/]|\/)?[\w./\\-_]+\.py|python3?\s+[\w./\\-_]+\.py)',
            query, re.IGNORECASE
        )

        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', answer, re.DOTALL)

        if target_path and code_blocks:
            code = max(code_blocks, key=len)
            yield {"type": "tool_call", "message": f"📝 Writing extracted code → {target_path}"}
            try:
                abs_path     = Path(os.path.abspath(target_path))
                project_root = Path(os.path.abspath(PROJECT_ROOT))
                # BUG-08 FIX: Path.is_relative_to() instead of startswith
                if not abs_path.is_relative_to(project_root):
                    yield {"type": "error",
                           "message": f"❌ Path traversal blocked: {target_path}"}
                else:
                    os.makedirs(abs_path.parent, exist_ok=True)
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
        skip  = {"node_modules", "__pycache__", ".git", "venv", ".venv",
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
