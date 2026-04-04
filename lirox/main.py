"""Lirox v2.0 — Multi-Agent Entry Point"""
import os
import sys
import time
import argparse


def check_dependencies():
    required = {
        "rich": "rich",
        "prompt_toolkit": "prompt-toolkit",
        "psutil": "psutil",
        "dotenv": "python-dotenv",
        "bs4": "beautifulsoup4",
        "lxml": "lxml",
    }
    missing = [pkg for mod, pkg in required.items() if not _try_import(mod.split(".")[0])]
    if missing:
        print(f"\n[!] Missing packages: {', '.join(missing)}")
        print(f"    Run: pip install {' '.join(missing)}\n")
        sys.exit(1)


def _try_import(m: str) -> bool:
    try:
        __import__(m)
        return True
    except ImportError:
        return False


check_dependencies()

from lirox.orchestrator.master import MasterOrchestrator
from lirox.ui.display import (
    show_welcome,
    show_status_card,
    show_thinking,
    show_agent_event,
    show_answer,
    error_panel,
    info_panel,
    success_message,
    confirm_prompt,
    console,
)
from lirox.utils.llm import available_providers
from lirox.config import APP_VERSION


def main():
    parser = argparse.ArgumentParser(description="Lirox v2 — Multi-Agent AI Kernel")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    parser.add_argument("--verbose", action="store_true", help="Verbose thinking output")
    parser.add_argument(
        "--no-thinking", action="store_true", help="Disable thinking engine"
    )
    args = parser.parse_args()
    if args.no_thinking:
        os.environ["THINKING_ENABLED"] = "false"

    from lirox.agent.profile import UserProfile

    profile = UserProfile()
    orchestrator = MasterOrchestrator(profile_data=profile.data)

    show_welcome()

    if not profile.is_setup() or args.setup:
        from lirox.ui.wizard import run_setup_wizard

        try:
            run_setup_wizard(profile)
        except KeyboardInterrupt:
            console.print("\n  [dim]Setup skipped.[/]")

    show_status_card(profile.data, available_providers())

    agent_name = profile.data.get("agent_name", "Lirox")
    last_int = 0.0

    while True:
        try:
            line = input(f"[{agent_name}] ✦ ").strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit", "/exit"):
                info_panel("Shutting down. Goodbye.")
                break
            if line.startswith("/"):
                handle_command(orchestrator, profile, line, verbose=args.verbose)
                continue
            process_query(orchestrator, line, verbose=args.verbose)
        except KeyboardInterrupt:
            now = time.time()
            if now - last_int < 2.0:
                print("\n[!] Force quit.")
                sys.exit(0)
            print("\n[!] Ctrl+C again to quit, or type /exit.")
            last_int = now
        except EOFError:
            info_panel("Shutting down. Goodbye.")
            break
        except Exception as e:
            error_panel("KERNEL ERROR", str(e))


def process_query(orch: MasterOrchestrator, query: str, verbose: bool = False):
    last_agent = "chat"
    for ev in orch.run(query):
        t = ev.type
        if t == "thinking" and ev.message:
            if verbose or len(ev.message) > 50:
                show_thinking(ev.message)
        elif t == "agent_start":
            last_agent = ev.agent
            show_agent_event(ev.agent, t, ev.message)
        elif t in ("tool_call", "tool_result", "agent_progress"):
            show_agent_event(ev.agent or last_agent, t, ev.message)
        elif t == "error":
            show_agent_event(ev.agent or last_agent, "error", ev.message)
        elif t == "done" and ev.message:
            show_answer(ev.message, agent=last_agent)


def handle_command(
    orch: MasterOrchestrator, profile, cmd: str, verbose: bool = False
):
    parts = cmd.lower().split()
    base = parts[0]

    if base == "/help":
        from rich.table import Table
        from rich.panel import Panel

        t = Table(
            show_header=True, header_style="bold #FFC107", border_style="dim"
        )
        t.add_column("Command", style="bold white")
        t.add_column("Description", style="dim white")
        for c, d in [
            ("/help", "Show this help"),
            ("/agents", "List all agents"),
            ("/models", "Show LLM providers"),
            ("/memory", "Memory stats"),
            ("/think <q>", "Run thinking engine on query"),
            ("/profile", "Show profile"),
            ("/reset", "Reset session memory"),
            ("/test", "Run diagnostics"),
            ("/exit", "Shutdown"),
        ]:
            t.add_row(c, d)
        console.print(
            Panel(
                t,
                title=f"[bold #FFC107]LIROX v{APP_VERSION} — COMMANDS[/]",
                border_style="#FFC107",
            )
        )

    elif base == "/agents":
        from rich.table import Table

        t = Table(show_header=True, header_style="bold #FFC107")
        t.add_column("Agent")
        t.add_column("Icon")
        t.add_column("Capability")
        for n, ic, d, c in [
            ("Finance", "📊", "Markets, stocks, portfolios, valuation", "cyan"),
            ("Code", "💻", "Write, debug, review, analyze code", "green"),
            ("Browser", "🌐", "Web navigation, content extraction", "orange1"),
            ("Research", "🔬", "Deep multi-source research", "medium_purple1"),
            ("Chat", "💬", "General conversation", "yellow"),
        ]:
            t.add_row(f"[{c}]{n}[/]", ic, d)
        console.print(t)
        console.print()

    elif base == "/models":
        providers = available_providers()
        info_panel(
            "AVAILABLE LLM PROVIDERS\n\n"
            + ("\n".join(f"  ✓ {p}" for p in providers) if providers else "  None configured")
        )

    elif base == "/memory":
        s = orch.memory.get_stats()
        info_panel(
            f"MEMORY STATS\n\n"
            f"  Buffer    : {s['buffer_size']} messages\n"
            f"  Long-term : {s['long_term_facts']} facts"
        )

    elif base == "/think":
        q = cmd[7:].strip()
        if q:
            from lirox.thinking.chain_of_thought import ThinkingEngine

            show_thinking(ThinkingEngine().reason(q))
        else:
            info_panel("Usage: /think <question>")

    elif base == "/profile":
        info_panel(f"PROFILE\n\n{profile.summary()}")

    elif base == "/reset":
        if confirm_prompt("Reset all session memory?"):
            orch.memory = type(orch.memory)()
            success_message("Memory reset.")

    elif base == "/test":
        info_panel("Running diagnostics...")
        for n, f in [
            ("Providers", lambda: ", ".join(available_providers()) or "None"),
            ("Memory", lambda: f"{orch.memory.get_stats()['buffer_size']} buffered"),
            ("Version", lambda: f"v{APP_VERSION}"),
            ("Agents", lambda: "Finance, Code, Browser, Research, Chat"),
        ]:
            try:
                console.print(f"  [green]✓[/] {n:22}: {f()}")
            except Exception as e:
                console.print(f"  [red]✖[/] {n:22}: {e}")
        success_message("Diagnostics complete.")

    else:
        console.print(f"  [dim]Unknown command: {base}. Type /help for options.[/]")
