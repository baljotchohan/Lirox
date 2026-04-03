"""
Lirox v0.7 — Enhanced Executor

Executes structured plans step-by-step with:
- Parallel execution of independent steps (ThreadPoolExecutor)
- Tool routing (terminal, browser/headless, file_io, llm)
- Dependency checking between steps
- Context chaining (step N output → step N+1 input) — up to 4000 chars
- Retry logic with exponential backoff
- Per-step status tracking and execution trace
- Output validation — detects tool failures even when no exception is thrown
- Headless browser for dynamic content & real-time data (v0.7)
"""

import time
import logging
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple, Any
from lirox.tools.terminal import run_command
from lirox.tools.browser import BrowserTool
from lirox.tools.file_io import FileIOTool
from lirox.utils.llm import generate_response
from lirox.utils.errors import ToolExecutionError, should_retry
from lirox.ui.display import execute_panel, update_plan_step, AgentSpinner
from lirox.config import MAX_RETRIES, RETRY_BACKOFF, CONTEXT_MAX_CHARS, PARALLEL_MAX_WORKERS

logger = logging.getLogger("lirox.executor")

# Patterns in tool output that indicate failure even without an exception
FAILURE_PATTERNS = [
    "[Blocked]",
    "Error:",
    "Error executing command:",
    "fatal:",
    "Permission denied",
    "File not found",
    "Access denied",
    "No such file or directory",
    "command not found",
    "not found",
    "could not extract a valid command",
    "No results found",
    "Connection timeout",
    "timed out",
]


class Executor:
    """Executes structured plans step-by-step with parallel independent steps."""

    # Keywords that REQUIRE headless browser (dynamic JS rendering)
    HEADLESS_KEYWORDS = [
        "dynamic", "javascript", "react", "spa", "real-time", "realtime",
        "live data", "form fill", "login", "scrape dynamic", "interactive",
        "render", "single page", "angular", "vue", "stock price", "live score",
        "headless", "automate", "fill form", "submit form",
    ]

    def __init__(self):
        self.browser  = BrowserTool()
        self.file_io  = FileIOTool()
        self.last_trace = []
        self._results_lock = threading.Lock()

        # v0.7: Headless browser tool (Lightpanda)
        self.headless_browser = None
        self.session_manager = None
        self.headless_available = False

        try:
            from lirox.tools.browser_tool import HeadlessBrowserTool
            self.headless_browser = HeadlessBrowserTool()
            self.headless_available = True
        except ImportError:
            pass

        # v0.7.1: Session manager for CDP-based browser automation
        try:
            from lirox.tools.browser_manager import BrowserSessionManager
            self.session_manager = BrowserSessionManager()
            if self.session_manager.is_available:
                self.headless_available = True
                logger.info("✓ Lightpanda browser available — headless mode enabled")
            else:
                logger.info("⚠ Lightpanda binary not found — HTTP-only fallback mode")
        except ImportError:
            logger.info("⚠ Browser session manager not available — HTTP-only fallback mode")

    def _is_output_failure(self, output: str) -> Tuple[bool, str]:
        """Check if tool output indicates failure despite no exception."""
        if not output:
            return False, ""
        output_lower = output.lower()
        for pattern in FAILURE_PATTERNS:
            if pattern.lower() in output_lower:
                return True, pattern
        return False, ""

    # ─── Main Entry Point ─────────────────────────────────────────────────────

    def execute_plan(self, plan: Dict[str, Any], provider: str = "auto", system_prompt: Optional[str] = None) -> Tuple[Dict[Any, Any], str]:
        """
        Execute all steps in a structured plan.
        Independent steps (no shared dependencies) are run in parallel.

        Returns: (results_dict, summary_string)
        """
        results = {}
        self.last_trace = []
        steps = plan.get("steps", [])

        # Build dependency graph for parallelism
        # Steps are grouped into waves: wave 0 has no deps, wave 1 depends on wave 0, etc.
        waves = self._build_execution_waves(steps)

        for wave in waves:
            if len(wave) == 1:
                # Single step — run directly
                step = wave[0]
                self._run_one_step(step, results, provider, system_prompt)
            else:
                # Multiple independent steps — run in parallel
                self._run_parallel_steps(wave, results, provider, system_prompt)

        summary = self._summarize_results(plan, results, provider, system_prompt)
        return results, summary

    def _build_execution_waves(self, steps: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Group steps into sequential waves where each wave contains
        steps that can run in parallel (no inter-wave dependencies).
        """
        if not steps:
            return []

        remaining = list(steps)
        completed_ids = set()
        waves = []

        while remaining:
            wave = []
            still_pending = []
            for step in remaining:
                deps = set(step.get("depends_on", []))
                if deps.issubset(completed_ids):
                    wave.append(step)
                else:
                    still_pending.append(step)

            if not wave:
                # Circular dependency or unresolvable — fall back to sequential
                wave = [remaining[0]]
                still_pending = remaining[1:]

            waves.append(wave)
            completed_ids.update(s["id"] for s in wave)
            remaining = still_pending

        return waves

    def _run_one_step(self, step: Dict[str, Any], results: Dict[Any, Any], provider: str, system_prompt: Optional[str]):
        step_id = step["id"]
        update_plan_step(step_id, step["task"], status="progress")
        start = time.time()

        if not self._check_dependencies(step, results):
            result = {"status": "skipped", "output": "Skipped: dependency failed", "duration": 0}
            results[step_id] = result
            update_plan_step(step_id, step["task"], status="skipped")
            self._add_trace(step, result)
            return

        try:
            result = self._execute_with_retry(step, results, provider, system_prompt)
        except Exception as e:
            result = {"status": "failed", "output": "", "error": str(e), "duration": 0}

        # Post-execution output validation
        if result["status"] == "success":
            is_failure, pattern = self._is_output_failure(result.get("output", ""))
            if is_failure:
                result["status"] = "failed"
                result["error"]  = f"Tool output indicates failure: {pattern}"

        result["duration"] = round(time.time() - start, 2)
        results[step_id] = result

        status = "success" if result["status"] == "success" else "failed"
        update_plan_step(step_id, step["task"], status=status)
        self._add_trace(step, result)

    def _run_parallel_steps(self, wave: List[Dict[str, Any]], results: Dict[Any, Any], provider: str, system_prompt: Optional[str]):
        """Run a wave of independent steps concurrently."""
        with ThreadPoolExecutor(max_workers=min(len(wave), PARALLEL_MAX_WORKERS)) as executor:
            wave_results = {}
            futures = {
                executor.submit(self._run_one_step_thread, step, results, provider, system_prompt): step
                for step in wave
                if self._check_dependencies(step, results)
            }
            done, not_done = concurrent.futures.wait(futures.keys(), timeout=120)

            for future in done:
                step = futures[future]
                try:
                    step_id, result = future.result()
                    wave_results[step_id] = result
                except Exception as e:
                    wave_results[step["id"]] = {
                        "status": "failed", "output": "",
                        "error": str(e), "duration": 0
                    }

            for future in not_done:
                step = futures[future]
                wave_results[step["id"]] = {
                    "status": "failed", "output": "Failed: Timeout (120s)",
                    "error": "Timeout", "duration": 120
                }

        # Merge wave results into main results dict (thread-safe)
        with self._results_lock:
            results.update(wave_results)
            for step in wave:
                if step["id"] in wave_results:
                    result = wave_results[step["id"]]
                    status = "success" if result["status"] == "success" else "failed"
                    update_plan_step(step["id"], step["task"], status=status)
                    self._add_trace(step, result)

    def _run_one_step_thread(self, step: Dict[str, Any], shared_results: Dict[Any, Any], provider: str, system_prompt: Optional[str]):
        """Thread-safe wrapper that returns (step_id, result)."""
        start = time.time()
        try:
            result = self._execute_with_retry(step, shared_results, provider, system_prompt)
        except Exception as e:
            result = {"status": "failed", "output": "", "error": str(e)}

        if result["status"] == "success":
            is_failure, pattern = self._is_output_failure(result.get("output", ""))
            if is_failure:
                result["status"] = "failed"
                result["error"]  = f"Tool output indicates failure: {pattern}"

        result["duration"] = round(time.time() - start, 2)
        return step["id"], result

    # ─── Retry Logic ─────────────────────────────────────────────────────────

    def _execute_with_retry(self, step: Dict[str, Any], previous_results: Dict[Any, Any], provider: str, system_prompt: Optional[str]):
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                output = self._execute_step(step, previous_results, provider, system_prompt)

                # Check for transient failure patterns before marking success
                is_failure, pattern = self._is_output_failure(output)
                if is_failure:
                    transient = ["timeout", "timed out", "connection", "rate limit"]
                    if any(t in pattern.lower() for t in transient) and attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_BACKOFF * (2 ** attempt))
                        continue

                return {"status": "success", "output": output, "attempt": attempt + 1}

            except ToolExecutionError as e:
                last_error = e
                if e.is_retryable and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
                    continue
                break
            except Exception as e:
                last_error = e
                if should_retry(e) and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
                    continue
                break

        return {"status": "failed", "output": "", "error": str(last_error), "attempts": MAX_RETRIES}

    # ─── Step Routing ────────────────────────────────────────────────────────

    def _execute_step(self, step: Dict[str, Any], previous_results: Dict[Any, Any], provider: str, system_prompt: Optional[str]) -> str:
        context = self._build_context(step, previous_results)
        tools   = step.get("tools", ["llm"])

        if "terminal" in tools:
            return self._run_terminal_step(step, context, provider, system_prompt)
        elif "browser" in tools:
            return self._run_browser_step(step, context, provider, system_prompt)
        elif "file_io" in tools:
            return self._run_file_step(step, context, provider, system_prompt)
        else:
            return self._run_llm_step(step, context, provider, system_prompt)

    def _run_terminal_step(self, step: Dict[str, Any], context: str, provider: str, system_prompt: Optional[str]) -> str:
        import platform
        os_name = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(
            platform.system(), platform.system()
        )
        cmd_prompt = (
            f"You are a terminal command generator. Extract the EXACT terminal command "
            f"to run from this task. Return ONLY the raw shell command on one line. "
            f"No explanation, no markdown, no backticks.\n\n"
            f"Task: {step['task']}\n"
            f"Context: {context[:500] if context else 'None'}\n"
            f"OS: {os_name}\n"
            f"Important: Use absolute paths. Return ONE command only."
        )
        command = generate_response(cmd_prompt, provider, system_prompt=system_prompt)
        command = command.strip().strip("`\"' \n")

        if command.startswith("```"):
            lines = command.split("\n")
            command = "\n".join(l for l in lines if not l.startswith("```")).strip()

        if not command or len(command) > 500:
            return f"Could not extract a valid command from: {step['task']}"

        if "\n" in command:
            command = command.split("\n")[0].strip()

        execute_panel(command)
        return run_command(command)

    def _run_browser_step(self, step: Dict[str, Any], context: str, provider: str, system_prompt: Optional[str]) -> str:
        task_lower = step["task"].lower()

        # v0.7: Detect if this task needs a headless browser
        needs_headless = any(kw in task_lower for kw in self.HEADLESS_KEYWORDS)

        # If headless is needed and available, route there
        if needs_headless and self.headless_browser and self.headless_browser._browser_available:
            return self._run_headless_browser_step(step, context, provider, system_prompt)

        if any(k in task_lower for k in ["research", "deep dive", "everything about", "latest on"]):
            query_prompt = (
                f"Extract a comprehensive research query from this task. "
                f"Return ONLY the query, nothing else.\n\n"
                f"Task: {step['task']}\n"
                f"Context: {context[:300] if context else 'None'}"
            )
            query = generate_response(query_prompt, provider, system_prompt=system_prompt).strip().strip("\"'")
            res = self.browser.research_topic(query)
            if isinstance(res, dict):
                return res.get("content", "No content found.")
            return res

        elif any(k in task_lower for k in ["search", "find", "lookup", "what is", "current", "live", "price"]):
            # Phase 2: Professional Data-Point Detection
            query_prompt = (
                f"Extract a concise search query. Return ONLY the search query.\n\n"
                f"Task: {step['task']}"
            )
            search_query = generate_response(query_prompt, provider, system_prompt=system_prompt).strip().strip("\"'")
            
            # Use the new verified fetching for data points
            res = self.browser.fetch_verified_data(step["task"], search_query)
            
            if res.get("type") == "verified_data":
                return res["content"]
            
            # If unverified, try one more time with a slightly different query
            if res.get("type") == "unverified_data":
                retry_query = f"current {search_query} real-time value"
                retry_res = self.browser.fetch_verified_data(step["task"], retry_query)
                if retry_res.get("type") == "verified_data":
                    return f"[Retry success] {retry_res['content']}"
                
                # Final fallback: return the best search results found
                formatted = [
                    f"{i}. {r['title']} ({r['domain']})\n   {r['url']}\n   {r['snippet']}"
                    for i, r in enumerate(res.get("sources", []), 1)
                ]
                return f"Searched for '{search_query}' but could not verify live data point.\nBest sources:\n" + "\n\n".join(formatted)

            return res.get("content", f"No results found for {search_query}")

        # Use the improved URL extractor from BrowserTool
        urls_in_context = self.browser.extract_urls_from_text(context) if context else []

        if any(k in task_lower for k in ["extract", "compare", "from pages", "summarize", "analyze results"]) and urls_in_context:
            # Phase 3: Parallel fetching for multi-URL tasks
            spinner = AgentSpinner(f"Scanning {len(urls_in_context[:4])} reliable sources...")
            spinner.start()
            
            top_urls = urls_in_context[:4]
            extracted = []
            
            def fetch_item(url):
                spinner.update_message(f"Extracting from {urlparse(url).netloc}...")
                if self.headless_browser and self.headless_browser._browser_available:
                    fetch = self.headless_browser.fetch_page(url, extract="markdown", timeout=15)
                    return f"--- Data from {url} ---\n{fetch.get('data', {}).get('markdown', '')[:3500]}\n"
                else:
                    content = self.browser.summarize_page(url)
                    return f"--- Data from {url} ---\n{content}\n"

            try:
                with ThreadPoolExecutor(max_workers=min(len(top_urls), 4)) as executor:
                    extracted = list(executor.map(fetch_item, top_urls))
            finally:
                spinner.stop()
                
            return "\n".join(extracted)

        elif "http" in task_lower:
            import re
            url_match = re.search(r'https?://\S+', step["task"])
            if url_match:
                url = url_match.group(0).rstrip(".,;)")
                # v0.7: prefer headless for direct URL fetch
                if self.headless_browser and self.headless_browser._browser_available:
                    fetch = self.headless_browser.fetch_page(url, extract="markdown")
                    content = fetch.get("data", {}).get("markdown", "")
                    return f"Content from {url}:\n{content[:5000]}"
                content = self.browser.summarize_page(url)
                return f"Content from {url}:\n{content}"

        # Fallback: derive search query from task
        search_prompt = (
            f"What search query should I use to complete this task? "
            f"Return ONLY the search query.\n\n"
            f"Task: {step['task']}"
        )
        query = generate_response(search_prompt, provider, system_prompt=system_prompt).strip().strip("\"'")
        results = self.browser.search_web(query, num_results=5)
        if results:
            formatted = [f"- {r['title']}: {r['snippet']}" for r in results]
            return f"Search for '{query}':\n" + "\n".join(formatted)

        return f"No results found for: {query}"

    def _run_headless_browser_step(self, step: Dict[str, Any], context: str, provider: str, system_prompt: Optional[str]) -> str:
        """v0.7: Route tasks requiring dynamic/JS rendering to the headless browser."""
        task_lower = step["task"].lower()

        # Extract URL from task
        import re
        url_match = re.search(r'https?://\S+', step["task"])

        # Form fill + submit
        if any(k in task_lower for k in ["form fill", "fill form", "login", "submit form"]):
            if url_match:
                url = url_match.group(0).rstrip(".,;)")
                # Use LLM to extract form field mappings
                form_prompt = (
                    f"Extract form field CSS selectors and values from this task. "
                    f"Return JSON: {{\"fields\": {{\"selector\": \"value\"}}, \"submit\": \"submit_selector\"}}\n\n"
                    f"Task: {step['task']}\n"
                    f"Context: {context[:500] if context else 'None'}"
                )
                result = self.headless_browser.interact_with_page(url, [
                    {"action": "extract", "type": "markdown"}
                ])
                return result.get("extracted_data", {}).get("markdown", "No content extracted")

        # Scrape / extract structured data
        if any(k in task_lower for k in ["scrape", "extract data", "structured data"]):
            if url_match:
                url = url_match.group(0).rstrip(".,;)")
                fetch = self.headless_browser.fetch_page(url, extract="all")
                data = fetch.get("data", {})
                parts = []
                if data.get("markdown"):
                    parts.append(data["markdown"][:5000])
                if data.get("tables"):
                    import json
                    parts.append(f"Tables: {json.dumps(data['tables'][:3], indent=2)[:3000]}")
                return "\n\n".join(parts) if parts else "No data extracted"

        # Real-time data / dynamic content
        if url_match:
            url = url_match.group(0).rstrip(".,;)")
            fetch = self.headless_browser.fetch_page(url, extract="markdown")
            content = fetch.get("data", {}).get("markdown", "")
            return f"[Headless Browser] Content from {url}:\n{content[:5000]}" if content else "No content extracted"

        # No URL — search first, then fetch with headless
        search_prompt = (
            f"Extract a concise search query from this task. Return ONLY the query.\n\n"
            f"Task: {step['task']}"
        )
        query = generate_response(search_prompt, provider, system_prompt=system_prompt).strip().strip("\"'")
        results = self.browser.search_web(query, num_results=3)
        if results:
            # Fetch top result with headless browser
            top_url = results[0].get("url", "")
            if top_url:
                fetch = self.headless_browser.fetch_page(top_url, extract="markdown")
                content = fetch.get("data", {}).get("markdown", "")
                result_text = f"Search: {query}\nTop result: {results[0]['title']} ({top_url})\n\n"
                result_text += content[:5000] if content else "Unable to extract content"
                return result_text

        return f"No results found for: {query}"

    def _run_file_step(self, step: Dict[str, Any], context: str, provider: str, system_prompt: Optional[str]) -> str:
        task_lower = step["task"].lower()

        if any(k in task_lower for k in ["read", "open", "load"]):
            file_prompt = (
                f"Extract the file path from this task. Return ONLY the path.\n\n"
                f"Task: {step['task']}\n"
                f"Context: {context[:300] if context else 'None'}"
            )
            path = generate_response(file_prompt, provider, system_prompt=system_prompt).strip().strip("\"'` \n")
            try:
                return self.file_io.read_file(path)
            except ToolExecutionError as e:
                return f"[file_io] {str(e)}"

        elif any(k in task_lower for k in ["write", "save", "create file", "output", "add", "store"]):
            content_to_write = context if context else ""
            if not context or len(context) < 50:
                write_prompt = (
                    f"Generate the content for this file. Return ONLY the content.\n\n"
                    f"Task: {step['task']}\n"
                    f"Context: {context[:1000] if context else 'None'}"
                )
                content_to_write = generate_response(write_prompt, provider, system_prompt=system_prompt)

            path_prompt = (
                f"Extract or suggest a file path for saving this content. "
                f"Return ONLY the absolute file path. Use 'outputs/' directory if unspecified. "
                f"Ensure the filename is descriptive but concise. No preamble.\n\n"
                f"Task: {step['task']}\n"
                f"Context: {context[:300] if context else 'None'}"
            )
            path = generate_response(path_prompt, provider, system_prompt=system_prompt).strip().strip("\"'` \n")
            if "/" not in path and "\\" not in path:
                path = f"outputs/{path}"

            try:
                return self.file_io.write_file(path, content_to_write)
            except ToolExecutionError as e:
                return f"[file_io] {str(e)}"

        elif any(k in task_lower for k in ["list", "ls", "directory", "folder"]):
            dir_prompt = (
                f"Extract the directory path to list. Return ONLY the path. Default to '.' "
                f"No explanation.\n\nTask: {step['task']}"
            )
            directory = generate_response(dir_prompt, provider, system_prompt=system_prompt).strip().strip("\"'` \n")
            try:
                files = self.file_io.list_files(directory)
                return f"Files in {directory}:\n" + "\n".join(files)
            except ToolExecutionError as e:
                return f"[file_io] {str(e)}"

        return self._run_llm_step(step, context, provider, system_prompt)

    def _run_llm_step(self, step: Dict[str, Any], context: str, provider: str, system_prompt: Optional[str]) -> str:
        reasoning_prompt = (
            f"Complete this task step and provide a concise, useful result.\n\n"
            f"Task: {step['task']}\n"
            f"Expected output: {step.get('expected_output', 'A clear result')}\n\n"
            f"RULES:\n"
            f"- Respond in plain text only. No JSON, no code blocks, no markdown.\n"
            f"- Be direct and factual. Get to the point immediately.\n"
            f"- If presenting data, use clean formatting (not JSON).\n"
        )
        if context:
            reasoning_prompt += f"\nContext from previous steps:\n{context[:3000]}"
        return generate_response(reasoning_prompt, provider, system_prompt=system_prompt)

    # ─── Context Building ─────────────────────────────────────────────────────

    def _build_context(self, step: Dict[str, Any], previous_results: Dict[Any, Any]) -> str:
        """Build context string from outputs of dependency steps (up to CONTEXT_MAX_CHARS)."""
        depends_on = step.get("depends_on", [])
        if not depends_on:
            return ""

        context_parts = []
        for dep_id in depends_on:
            dep_result = previous_results.get(dep_id, {})
            if dep_result.get("status") == "success":
                output = dep_result.get("output", "")
                if len(output) > CONTEXT_MAX_CHARS:
                    # [FIX #4] Explicit Truncation Logging
                    removed_chars = len(output) - CONTEXT_MAX_CHARS
                    output = output[:CONTEXT_MAX_CHARS] + f"\n\n... [TRUNCATED: {removed_chars} chars removed]"
                context_parts.append(f"[Step {dep_id} output]: {output}")

        return "\n\n".join(context_parts)

    def _check_dependencies(self, step: Dict[str, Any], results: Dict[Any, Any]) -> bool:
        depends_on = step.get("depends_on", [])
        for dep_id in depends_on:
            dep_result = results.get(dep_id, {})
            if dep_result.get("status") in ("failed", "skipped"):
                return False
        return True

    # ─── Summary & Trace ─────────────────────────────────────────────────────

    def _summarize_results(self, plan: Dict[str, Any], results: Dict[Any, Any], provider: str, system_prompt: Optional[str]) -> str:
        lines = []
        successes = 0
        total = len(results)

        for step in plan.get("steps", []):
            step_id  = step["id"]
            result   = results.get(step_id, {})
            status   = result.get("status", "unknown")
            duration = result.get("duration", 0)
            icon = "✓" if status == "success" else "✗" if status == "failed" else "⊘"
            lines.append(f"{icon} Step {step_id}: {step['task'][:70]} ({duration}s)")
            if status == "success":
                successes += 1

        summary = (
            f"### 📊 Execution Summary\n\n"
            f"**Goal**: {plan.get('goal', 'Unknown')}\n\n"
            f"**Status**: {successes}/{total} steps successfully completed\n\n"
            "```text\n"
        ) + "\n".join(lines) + "\n```"

        if total > 0:
            all_outputs = []
            for step in plan.get("steps", []):
                result = results.get(step["id"], {})
                status = result.get("status", "unknown")
                output = result.get("output", "")[:300]
                error  = result.get("error", "")
                all_outputs.append(
                    f"Step {step['id']} ({step['task']}): "
                    f"status={status}, output={output}"
                    f"{f', error={error}' if error else ''}"
                )
            try:
                summary_prompt = (
                    f"Summarize what was accomplished in 2-3 clear sentences. "
                    f"Be HONEST — if steps failed or were blocked, say so clearly.\n\n"
                    f"Goal: {plan.get('goal', '')}\n"
                    f"Results ({successes}/{total} succeeded):\n" + "\n".join(all_outputs) +
                    f"\n\nCRITICAL RULES:\n"
                    f"- Write ONLY plain English sentences. No JSON, no code blocks.\n"
                    f"- Do NOT include metadata, mode, intent, tool_preference, or any machine-readable data.\n"
                    f"- Do NOT wrap your response in ```json or ``` blocks.\n"
                    f"- State the key result (e.g. the price, the data found) clearly.\n"
                    f"- Keep it under 4 sentences. Be professional and direct."
                )
                narrative = generate_response(summary_prompt, provider, system_prompt=system_prompt)

                # Strip any JSON blocks that leaked through
                narrative = self._strip_json_blocks(narrative)

                summary += f"\n\n### 📝 Result\n\n{narrative}"
            except Exception:
                pass

        return summary

    @staticmethod
    def _strip_json_blocks(text: str) -> str:
        """Remove any JSON/code blocks that leaked into plain text output."""
        import re
        # Remove ```json ... ``` blocks
        text = re.sub(r'```(?:json)?\s*\n?\{[^}]*\}\s*\n?```', '', text, flags=re.DOTALL)
        # Remove standalone JSON objects at the end
        text = re.sub(r'\n\s*\{\s*"\w+"\s*:.*\}\s*$', '', text, flags=re.DOTALL)
        return text.strip()

    def _add_trace(self, step: Dict[str, Any], result: Dict[Any, Any]):
        self.last_trace.append({
            "step_id":       step["id"],
            "task":          step["task"],
            "tools":         step.get("tools", []),
            "status":        result.get("status", "unknown"),
            "output_preview":result.get("output", "")[:200],
            "error":         result.get("error", ""),
            "duration":      result.get("duration", 0),
            "attempts":      result.get("attempt", result.get("attempts", 1)),
        })

        return "\n".join(lines)

    def get_browser_token_status(self) -> Optional[Dict[str, Any]]:
        """v0.7.1: Retrieve the current token rate-limit status for UI display."""
        if self.headless_browser and hasattr(self.headless_browser, "_security") and self.headless_browser._security:
            return self.headless_browser._security.get_token_status()
        return None
