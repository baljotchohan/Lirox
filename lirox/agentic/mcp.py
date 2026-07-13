"""Model Context Protocol (MCP) client — stdio transport.

MCP is the emerging industry standard (Anthropic, adopted by Claude Code, Cline,
Goose, Cursor, …) for connecting agents to external tools. A server exposes
tools via JSON-RPC 2.0; the client discovers them with ``tools/list`` and invokes
them with ``tools/call``. This gives Lirox instant access to the large open
ecosystem of MCP servers (filesystem, git, github, postgres, puppeteer, slack,
brave-search, and hundreds more) with zero bespoke integration each.

This module implements a dependency-free stdio client (no SDK required) and
registers every discovered tool into a Lirox :class:`ToolRegistry`, namespaced
as ``mcp.<server>.<tool>``.

Config (``~/.lirox/mcp.json`` — same shape as Claude Desktop's mcpServers):

    {
      "mcpServers": {
        "filesystem": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
          "env": {}
        }
      }
    }
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.verify.receipt import ExecutionReceipt

_logger = logging.getLogger("lirox.agentic.mcp")

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "lirox", "version": "1.1"}


def config_path() -> Path:
    override = os.getenv("LIROX_MCP_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(os.path.expanduser("~/.lirox/mcp.json"))


def load_config() -> Dict[str, Any]:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("mcpServers", {})
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Bad MCP config %s: %s", p, exc)
        return {}


class MCPStdioClient:
    """A minimal JSON-RPC-over-stdio MCP client for one server process."""

    def __init__(self, name: str, command: str, args: List[str],
                 env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None,
                 timeout: float = 30.0) -> None:
        self.name = name
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}
        self.cwd = cwd
        self.timeout = timeout
        self.proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._lock = threading.Lock()
        self.tools: List[Dict[str, Any]] = []

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self) -> None:
        exe = shutil.which(self.command) or self.command
        self.proc = subprocess.Popen(
            [exe, *self.args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=self.env, cwd=self.cwd, text=True, bufsize=1,
        )
        # handshake
        self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        })
        self._notify("notifications/initialized", {})
        self.tools = self.list_tools()

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                try:
                    self.proc.kill()
                except Exception:  # noqa: BLE001
                    pass

    # ── JSON-RPC plumbing ─────────────────────────────────────────────────
    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _write(self, obj: Dict[str, Any]) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _notify(self, method: str, params: Dict[str, Any]) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        assert self.proc and self.proc.stdout
        with self._lock:
            rid = self._next_id()
            self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
            # Read until we see the matching response id (skip notifications).
            deadline = self.timeout
            import time
            end = time.time() + deadline
            while time.time() < end:
                line = self.proc.stdout.readline()
                if not line:
                    raise RuntimeError(f"MCP server '{self.name}' closed the connection")
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == rid:
                    if "error" in msg:
                        raise RuntimeError(msg["error"].get("message", "MCP error"))
                    return msg.get("result", {})
            raise TimeoutError(f"MCP server '{self.name}' timed out on {method}")

    # ── MCP methods ───────────────────────────────────────────────────────
    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._request("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, tool: str, arguments: Dict[str, Any]) -> str:
        result = self._request("tools/call", {"name": tool, "arguments": arguments})
        # MCP returns content parts; flatten text parts.
        parts = result.get("content", [])
        texts = []
        for part in parts:
            if part.get("type") == "text":
                texts.append(part.get("text", ""))
            else:
                texts.append(json.dumps(part, default=str))
        out = "\n".join(texts) if texts else json.dumps(result, default=str)
        if result.get("isError"):
            raise RuntimeError(out or "tool reported error")
        return out


class MCPHttpClient:
    """Minimal MCP client over the Streamable HTTP transport (JSON-RPC 2.0
    POSTed to a single endpoint; the server may reply with a plain JSON body
    or a ``text/event-stream`` of JSON-RPC messages). Dependency-free — uses
    urllib, matching the rest of Lirox's zero-extra-dep network code."""

    def __init__(self, name: str, url: str, headers: Optional[Dict[str, str]] = None,
                 timeout: float = 30.0) -> None:
        self.name = name
        self.url = url
        self.headers = dict(headers or {})
        self.timeout = timeout
        self._id = 0
        self._session_id: Optional[str] = None
        self.tools: List[Dict[str, Any]] = []

    def start(self) -> None:
        self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        })
        self._notify("notifications/initialized", {})
        self.tools = self.list_tools()

    def stop(self) -> None:
        pass  # stateless HTTP — nothing to tear down

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _post(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        import urllib.request
        import urllib.error

        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._session_id = sid
                ctype = resp.headers.get("Content-Type", "")
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:  # noqa: BLE001
            raise RuntimeError(f"MCP HTTP {exc.code}: {exc.reason}") from exc

        if "event-stream" in ctype:
            return self._parse_sse(raw)
        if not raw.strip():
            return None  # notification — no response body expected
        return json.loads(raw)

    @staticmethod
    def _parse_sse(raw: str) -> Optional[Dict[str, Any]]:
        """Take the last JSON-RPC message out of an SSE event stream."""
        last = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                chunk = line[len("data:"):].strip()
                if not chunk:
                    continue
                try:
                    last = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
        return last

    def _notify(self, method: str, params: Dict[str, Any]) -> None:
        self._post({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        rid = self._next_id()
        result = self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        if result is None:
            raise RuntimeError(f"MCP server '{self.name}' gave no response to {method}")
        if "error" in result:
            raise RuntimeError(result["error"].get("message", "MCP error"))
        return result.get("result", {})

    def list_tools(self) -> List[Dict[str, Any]]:
        return self._request("tools/list", {}).get("tools", [])

    def call_tool(self, tool: str, arguments: Dict[str, Any]) -> str:
        result = self._request("tools/call", {"name": tool, "arguments": arguments})
        parts = result.get("content", [])
        texts = []
        for part in parts:
            if part.get("type") == "text":
                texts.append(part.get("text", ""))
            else:
                texts.append(json.dumps(part, default=str))
        out = "\n".join(texts) if texts else json.dumps(result, default=str)
        if result.get("isError"):
            raise RuntimeError(out or "tool reported error")
        return out


# Keep started clients alive for the process lifetime.
_ACTIVE: Dict[str, Any] = {}


def _mcp_json_schema_to_params(schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Translate an MCP inputSchema (JSON Schema) into Lirox tool params."""
    props = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])
    out: Dict[str, Dict[str, Any]] = {}
    for name, spec in props.items():
        out[name] = {
            "type": spec.get("type", "string"),
            "description": spec.get("description", ""),
            "required": name in required,
        }
    return out


def register_mcp_tools(registry, servers: Optional[Dict[str, Any]] = None) -> int:
    """Start every configured MCP server and register its tools into
    ``registry``. Returns the number of tools registered. Failures per-server
    are logged and skipped (never fatal)."""
    from lirox.agentic.tools import DANGER_SHELL  # MCP tools can do anything → treat as shell-danger

    servers = servers if servers is not None else load_config()
    if not servers:
        return 0

    count = 0
    for name, cfg in servers.items():
        try:
            if cfg.get("url"):
                client = MCPHttpClient(
                    name=name, url=cfg["url"], headers=cfg.get("headers", {}),
                )
            else:
                client = MCPStdioClient(
                    name=name,
                    command=cfg.get("command", ""),
                    args=cfg.get("args", []),
                    env=cfg.get("env", {}),
                    cwd=cfg.get("cwd"),
                )
            client.start()
            _ACTIVE[name] = client
        except Exception as exc:  # noqa: BLE001
            _logger.warning("MCP server '%s' failed to start: %s", name, exc)
            continue

        for tool in client.tools:
            tname = tool.get("name", "")
            if not tname:
                continue
            full = f"mcp.{name}.{tname}"
            params = _mcp_json_schema_to_params(tool.get("inputSchema", {}))

            def _make_handler(_client, _tool: str):
                def _handler(**kwargs) -> ExecutionReceipt:
                    try:
                        out = _client.call_tool(_tool, kwargs)
                        return ExecutionReceipt(tool=f"mcp.{_client.name}.{_tool}",
                                                ok=True, verified=True, message=out[:6000])
                    except Exception as exc:  # noqa: BLE001
                        return ExecutionReceipt(tool=f"mcp.{_client.name}.{_tool}",
                                                ok=False, error=str(exc))
                return _handler

            registry.add(
                full,
                f"[MCP:{name}] {tool.get('description', tname)}",
                params,
                _make_handler(client, tname),
                danger=DANGER_SHELL,
            )
            count += 1

    if count:
        _logger.info("Registered %d MCP tool(s) from %d server(s).", count, len(_ACTIVE))
    return count


def shutdown_mcp() -> None:
    for client in _ACTIVE.values():
        client.stop()
    _ACTIVE.clear()
