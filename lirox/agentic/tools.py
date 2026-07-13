"""Agentic tool registry.

Wraps Lirox's existing *verified* tool functions (shell, file, search, code)
into a uniform, LLM-callable tool surface. Each tool declares a JSON-schema-ish
parameter spec so the ReAct loop can render an accurate tool manifest into the
system prompt, and a danger class so the permission layer can gate it.

Every handler returns an :class:`ExecutionReceipt` (or a plain string, which is
wrapped). The loop feeds ``receipt.as_llm_context()`` back to the model as the
observation for the next step — so the agent always sees an honest
SUCCESS/FAILED signal, never a hallucinated one.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from lirox.verify.receipt import ExecutionReceipt

_logger = logging.getLogger("lirox.agentic.tools")


# Danger classes drive the permission layer.
DANGER_SAFE = "safe"        # read-only, no side effects (read, list, search)
DANGER_WRITE = "write"      # mutates the filesystem
DANGER_SHELL = "shell"      # executes arbitrary commands / code
DANGER_NETWORK = "network"  # reaches the internet


@dataclass
class ToolSpec:
    """A single callable tool exposed to the agent."""

    name: str
    description: str
    parameters: Dict[str, Dict[str, Any]]  # name -> {type, description, required}
    handler: Callable[..., Any]
    danger: str = DANGER_SAFE

    def signature(self) -> str:
        """One-line manifest entry the model reads to learn the tool."""
        args = ", ".join(
            f"{n}: {p.get('type', 'string')}"
            + ("" if p.get("required", True) else "?")
            for n, p in self.parameters.items()
        )
        return f"{self.name}({args}) — {self.description}"

    def detailed(self) -> str:
        """Multi-line description with per-argument docs."""
        lines = [f"• {self.name} — {self.description}"]
        for n, p in self.parameters.items():
            req = "required" if p.get("required", True) else "optional"
            lines.append(
                f"    - {n} ({p.get('type', 'string')}, {req}): "
                f"{p.get('description', '')}"
            )
        return "\n".join(lines)


class ToolRegistry:
    """Holds tools and dispatches validated calls to them."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    # ── registration ──────────────────────────────────────────────────────
    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def add(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Dict[str, Any]],
        handler: Callable[..., Any],
        danger: str = DANGER_SAFE,
    ) -> None:
        self.register(ToolSpec(name, description, parameters, handler, danger))

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    # ── introspection ─────────────────────────────────────────────────────
    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def manifest(self, detailed: bool = True) -> str:
        """The tool list rendered into the agent's system prompt."""
        if not self._tools:
            return "(no tools available)"
        renderer = (lambda t: t.detailed()) if detailed else (lambda t: "  " + t.signature())
        return "\n".join(renderer(t) for t in self._tools.values())

    # ── dispatch ──────────────────────────────────────────────────────────
    def call(self, name: str, arguments: Dict[str, Any]) -> ExecutionReceipt:
        """Invoke a tool by name with a dict of arguments. Always returns a
        receipt — validation and handler errors become FAILED receipts."""
        spec = self._tools.get(name)
        if spec is None:
            return ExecutionReceipt(
                tool=name, ok=False, verified=False,
                error=f"Unknown tool '{name}'. Available: {', '.join(self.names())}",
            )

        # Validate required arguments are present.
        missing = [
            n for n, p in spec.parameters.items()
            if p.get("required", True) and n not in arguments
        ]
        if missing:
            return ExecutionReceipt(
                tool=name, ok=False, verified=False,
                error=f"Missing required argument(s): {', '.join(missing)}",
            )

        # Drop unexpected arguments rather than crashing the handler.
        clean = {k: v for k, v in arguments.items() if k in spec.parameters}
        try:
            result = spec.handler(**clean)
        except TypeError as exc:
            return ExecutionReceipt(
                tool=name, ok=False, verified=False,
                error=f"Bad arguments for {name}: {exc}",
            )
        except Exception as exc:  # noqa: BLE001 — handlers must never crash the loop
            _logger.exception("Tool %s raised", name)
            return ExecutionReceipt(
                tool=name, ok=False, verified=False, error=f"{type(exc).__name__}: {exc}",
            )

        if isinstance(result, ExecutionReceipt):
            return result
        # Plain string / other → wrap as a verified informational receipt.
        return ExecutionReceipt(
            tool=name, ok=True, verified=True, message=str(result),
        )


# ══════════════════════════════════════════════════════════════════════════
# Built-in tools — thin adapters over Lirox's existing verified functions.
# ══════════════════════════════════════════════════════════════════════════

def _workspace() -> str:
    from lirox.config import WORKSPACE_DIR
    return os.getenv("LIROX_WORKSPACE", WORKSPACE_DIR)


def _t_read_file(path: str, max_chars: int = 8000) -> ExecutionReceipt:
    from lirox.tools.file_tools import file_read_verified
    return file_read_verified(path, max_chars=int(max_chars))


def _t_write_file(path: str, content: str) -> ExecutionReceipt:
    from lirox.tools.file_tools import file_write_verified
    return file_write_verified(path, content)


def _t_edit_file(path: str, search: str, replace: str) -> ExecutionReceipt:
    # Robust fuzzy search-replace editor (see editor.py).
    from lirox.agentic.editor import edit_file
    return edit_file(path, search, replace)


def _t_list_dir(path: str = ".", depth: int = 2) -> ExecutionReceipt:
    from lirox.tools.file_tools import list_directory_tree
    text = list_directory_tree(path or _workspace(), depth=int(depth))
    return ExecutionReceipt(tool="list_dir", ok=True, verified=True, message=text)


def _t_search_files(root: str = ".", query: str = "", max_results: int = 40) -> ExecutionReceipt:
    from lirox.tools.file_tools import file_search
    text = file_search(root or _workspace(), query, max_results=int(max_results))
    return ExecutionReceipt(tool="search_files", ok=True, verified=True, message=text)


def _t_shell(command: str, cwd: str = "") -> ExecutionReceipt:
    from lirox.tools.shell_verified import shell_run_verified
    return shell_run_verified(command, cwd=cwd or _workspace())


def _t_run_python(code: str, timeout: int = 10) -> ExecutionReceipt:
    from lirox.tools.code_executor import CodeExecutor
    try:
        result = CodeExecutor().execute_python(code, timeout=int(timeout))
        ok = bool(result.get("success"))
        message = result.get("output", "") or ""
        if result.get("error"):
            message = f"{message}\nSTDERR: {result['error']}" if message else result["error"]
        return ExecutionReceipt(
            tool="run_python", ok=ok, verified=True, message=message.strip()[:4000],
            error="" if ok else (result.get("error") or "non-zero exit"),
            details={"exit_code": result.get("exit_code", -1)},
        )
    except Exception as exc:  # noqa: BLE001
        return ExecutionReceipt(tool="run_python", ok=False, error=str(exc))


def _t_web_search(query: str, max_results: int = 5) -> ExecutionReceipt:
    # Prefer Tavily (richer), fall back to DuckDuckGo.
    try:
        from lirox.tools.search.tavily import search_tavily
        if os.getenv("TAVILY_API_KEY"):
            return ExecutionReceipt(tool="web_search", ok=True, verified=True,
                                    message=search_tavily(query, max_results=int(max_results)))
    except Exception:  # noqa: BLE001
        pass
    try:
        from lirox.tools.search.duckduckgo import search as ddg
        rows = ddg(query, max_results=int(max_results))
        lines = [f"- {r.get('title', '')}: {r.get('href', r.get('url', ''))}\n  {r.get('body', '')[:200]}"
                 for r in rows]
        return ExecutionReceipt(tool="web_search", ok=True, verified=True,
                                message="\n".join(lines) or "(no results)")
    except Exception as exc:  # noqa: BLE001
        return ExecutionReceipt(tool="web_search", ok=False, error=str(exc))


def register_builtin_tools(reg: ToolRegistry) -> None:
    """Register the standard local toolset onto ``reg``."""
    reg.add("read_file", "Read a text file and return its contents.",
            {"path": {"type": "string", "description": "File path (absolute or workspace-relative)."},
             "max_chars": {"type": "int", "description": "Max characters to read.", "required": False}},
            _t_read_file, danger=DANGER_SAFE)

    reg.add("write_file", "Create or overwrite a file with the given content.",
            {"path": {"type": "string", "description": "Destination path."},
             "content": {"type": "string", "description": "Full file content to write."}},
            _t_write_file, danger=DANGER_WRITE)

    reg.add("edit_file",
            "Make a targeted edit by replacing an exact snippet. Uses fuzzy "
            "whitespace-tolerant matching; falls back safely if the snippet is "
            "ambiguous. Prefer this over write_file for changes to existing files.",
            {"path": {"type": "string", "description": "File to edit."},
             "search": {"type": "string", "description": "Existing snippet to locate (a few unique lines)."},
             "replace": {"type": "string", "description": "Replacement text."}},
            _t_edit_file, danger=DANGER_WRITE)

    reg.add("list_dir", "List a directory tree.",
            {"path": {"type": "string", "description": "Directory (defaults to workspace).", "required": False},
             "depth": {"type": "int", "description": "Recursion depth.", "required": False}},
            _t_list_dir, danger=DANGER_SAFE)

    reg.add("search_files", "Search file contents recursively for a string/regex.",
            {"root": {"type": "string", "description": "Root directory.", "required": False},
             "query": {"type": "string", "description": "Text to find."},
             "max_results": {"type": "int", "description": "Result cap.", "required": False}},
            _t_search_files, danger=DANGER_SAFE)

    reg.add("shell", "Run a shell command in the workspace (sandboxed & audited).",
            {"command": {"type": "string", "description": "Command line to execute."},
             "cwd": {"type": "string", "description": "Working directory.", "required": False}},
            _t_shell, danger=DANGER_SHELL)

    reg.add("run_python", "Execute a snippet of Python and capture its output.",
            {"code": {"type": "string", "description": "Python source to run."},
             "timeout": {"type": "int", "description": "Max seconds before killing it.", "required": False}},
            _t_run_python, danger=DANGER_SHELL)

    reg.add("web_search", "Search the web and return top results.",
            {"query": {"type": "string", "description": "Search query."},
             "max_results": {"type": "int", "description": "How many results.", "required": False}},
            _t_web_search, danger=DANGER_NETWORK)


def default_registry(include_mcp: bool = True, include_extras: bool = True) -> ToolRegistry:
    """A registry preloaded with the built-in toolset (browser + delegation),
    and MCP tools if configured and available)."""
    reg = ToolRegistry()
    register_builtin_tools(reg)
    if include_extras:
        try:
            from lirox.agentic.extras import register_browser_tool, register_delegate_tool
            from lirox.agentic.repo_map import register_repo_map_tool
            register_browser_tool(reg)
            register_delegate_tool(reg)
            register_repo_map_tool(reg)
        except Exception as exc:  # noqa: BLE001 — extras are optional
            _logger.debug("Extra tools not loaded: %s", exc)
    if include_mcp:
        try:
            from lirox.agentic.mcp import register_mcp_tools
            register_mcp_tools(reg)
        except Exception as exc:  # noqa: BLE001 — MCP is optional
            _logger.debug("MCP tools not loaded: %s", exc)
    return reg
