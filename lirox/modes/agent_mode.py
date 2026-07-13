"""Agent Mode — /agent <task>

Runs Lirox's autonomous ReAct loop (lirox.agentic) for a task: the model plans,
picks tools, observes results, and iterates until done — instead of the single
keyword-dispatched tool call used by the rest of the assistant.

This is intentionally a thin rendering layer over lirox.agentic.loop.AgentLoop;
all the actual autonomy lives there.
"""
from __future__ import annotations

import logging
from typing import Optional

_logger = logging.getLogger("lirox.modes.agent_mode")

# Session-scoped permission manager so /agent-mode persists across calls
# within one Lirox process.
_perms = None


def _get_perms():
    global _perms
    if _perms is None:
        from lirox.agentic.permissions import PermissionManager, PermissionMode
        _perms = PermissionManager(PermissionMode.DEFAULT)
    return _perms


def set_agent_mode(mode: str) -> str:
    """Change the graduated permission mode for future /agent runs."""
    perms = _get_perms()
    perms.set_mode(mode)
    return perms.mode.value


def get_agent_mode() -> str:
    return _get_perms().mode.value


def _console_approver(console):
    """Build an approver callback that asks the user via the terminal."""
    def _ask(tool_name: str, args: dict) -> bool:
        from rich.prompt import Confirm
        preview = ", ".join(f"{k}={str(v)[:60]}" for k, v in args.items())
        console.print(f"  [bold #FFC107]⚠ Approval needed:[/] {tool_name}({preview})")
        try:
            return Confirm.ask("  Allow this action?", default=False)
        except Exception:  # noqa: BLE001
            return False
    return _ask


def agent_handle(cmd: str, console, provider: str = "auto", max_steps: int = 25) -> None:
    """Entry point for the /agent slash command."""
    from lirox.agentic.loop import AgentLoop
    from lirox.agentic.tools import default_registry

    parts = cmd.strip().split(maxsplit=1)
    task = parts[1].strip() if len(parts) > 1 else ""

    if not task:
        console.print("  [dim]Usage: /agent <task description>[/]")
        console.print(f"  [dim]Current mode: {get_agent_mode()} — change with /agent-mode <plan|default|acceptEdits|auto|bypass>[/]")
        return

    perms = _get_perms()
    perms.approver = _console_approver(console)

    console.print(f"\n  [bold #FFD700]🤖 Agent[/] [dim]({perms.mode.value} mode)[/] — {task}\n")

    registry = default_registry()
    loop = AgentLoop(registry=registry, permissions=perms, provider=provider, max_steps=max_steps)

    finished = False
    try:
        for step in loop.run(task):
            _render_step(console, step)
            if step.kind == "final":
                finished = True
    except KeyboardInterrupt:
        console.print("\n  [dim]Agent interrupted.[/]")
        return

    if not finished:
        console.print("\n  [bold #FFC107]⚠ Stopped without an explicit finish.[/]")


def _render_step(console, step) -> None:
    from rich.markup import escape

    if step.kind == "thought":
        console.print(f"  [dim]  💭 {escape(step.text)}[/]")
    elif step.kind == "action":
        args_preview = ", ".join(f"{k}={str(v)[:50]}" for k, v in (step.args or {}).items())
        console.print(f"  [#00BFFF]  ├─ 🔧 {escape(step.tool)}({escape(args_preview)})[/]")
    elif step.kind == "observation":
        console.print(f"  [dim]  │  {escape(step.text[:300])}[/]")
    elif step.kind == "denied":
        console.print(f"  [bold #FF6B6B]  ├─ 🚫 {escape(step.text)}[/]")
    elif step.kind == "critique":
        console.print(f"  [dim italic]  ⚖ QA check: {escape(step.text)}[/]")
    elif step.kind == "learned":
        console.print(f"  [bold #A78BFA]  ✨ {escape(step.text)}[/]")
    elif step.kind == "status":
        console.print(f"  [dim]  … {escape(step.text)}[/]")
    elif step.kind == "final":
        console.print(f"\n  [bold #10b981]✓ {escape(step.text)}[/]\n")
    elif step.kind == "error":
        console.print(f"  [bold red]  ✗ {escape(step.text)}[/]")
