"""Lirox v3.0 — Multi-Agent Entry Point: Mode system, sessions, history, desktop control"""
import os
import sys
import time
import argparse


def check_dependencies():
    required = {
        "rich":          "rich",
        "prompt_toolkit": "prompt-toolkit",
        "psutil":        "psutil",
        "dotenv":        "python-dotenv",
        "bs4":           "beautifulsoup4",
        "lxml":          "lxml",
        "requests":      "requests",
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
from lirox.config import APP_VERSION, ThinkingMode


# ── Mode Display Helpers ──────────────────────────────────────────────────────

MODE_LABELS = {
    ThinkingMode.FAST:    "[bold cyan]⚡ FAST[/]",
    ThinkingMode.THINK:   "[bold yellow]🧠 THINK[/]",
    ThinkingMode.COMPLEX: "[bold magenta]🔮 COMPLEX[/]",
}

MODE_DESCRIPTIONS = {
    ThinkingMode.FAST:    "Quick answers, minimal reasoning",
    ThinkingMode.THINK:   "Detailed, thoughtful responses",
    ThinkingMode.COMPLEX: "Full structured output: plan + analysis + recommendation",
}


def get_prompt_label(agent_name: str, mode: str) -> list:
    mode_emoji = {"fast": "⚡", "think": "🧠", "complex": "🔮"}.get(mode, "✦")
    return [
        ('class:prompt',  f"[{agent_name}] "),
        ('class:mode',    f"{mode_emoji} "),
        ('class:symbol',  "✦ "),
    ]


def main():
    check_dependencies()

    parser = argparse.ArgumentParser(description="Lirox v3.0 — Multi-Agent AI Kernel")
    parser.add_argument("--setup",        action="store_true", help="Run setup wizard")
    parser.add_argument("--verbose",      action="store_true", help="Verbose thinking output")
    parser.add_argument("--no-thinking",  action="store_true", help="Disable thinking engine")
    parser.add_argument("--mode",         default="think",     help="Thinking mode: fast|think|complex")
    args = parser.parse_args()

    if args.no_thinking:
        os.environ["THINKING_ENABLED"] = "false"

    from lirox.agent.profile import UserProfile
    profile      = UserProfile()
    orchestrator = MasterOrchestrator(profile_data=profile.data)

    # Set initial mode from args
    if args.mode in (ThinkingMode.FAST, ThinkingMode.THINK, ThinkingMode.COMPLEX):
        orchestrator.thinking_mode = args.mode

    show_welcome()

    if not profile.is_setup() or args.setup:
        from lirox.ui.wizard import run_setup_wizard
        try:
            run_setup_wizard(profile)
        except KeyboardInterrupt:
            console.print("\n  [dim]Setup skipped.[/]")

    show_status_card(profile.data, available_providers())
    _show_mode_status(orchestrator.thinking_mode)

    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.completion import Completer, Completion

    agent_name = profile.data.get("agent_name", "Lirox")
    last_int   = 0.0

    style = Style.from_dict({
        'prompt': 'ansiyellow bold',
        'mode':   'ansicyan',
        'symbol': 'ansiyellow',
    })
    
    commands = [
        "/help",
        "/mode fast", "/mode think", "/mode complex",
        "/agent finance", "/agent code", "/agent browser", "/agent research", "/agent chat",
        "/agents", "/history", "/session", "/models", "/memory", "/think", "/profile",
        "/reset", "/desktop", "/test", "/import-memory", "/export-profile",
        "/uninstall", "/update", "/exit"
    ]
    
    class SlashCommandCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor.lstrip()
            if not text.startswith('/'):
                return
            
            text_lower = text.lower()
            for cmd in commands:
                if cmd.startswith(text_lower):
                    yield Completion(cmd, start_position=-len(text))

    session = PromptSession(completer=SlashCommandCompleter(), complete_while_typing=True)

    while True:
        try:
            current_mode = orchestrator.thinking_mode
            prompt_label = get_prompt_label(agent_name, current_mode)

            line = session.prompt(prompt_label, style=style).strip()
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


def _show_mode_status(mode: str):
    label = MODE_LABELS.get(mode, mode)
    desc  = MODE_DESCRIPTIONS.get(mode, "")
    console.print(f"  Mode: {label}  [dim]{desc}[/]")
    console.print(f"  [dim]Switch: /mode fast | /mode think | /mode complex[/]")
    console.print()


def process_query(orch: MasterOrchestrator, query: str, verbose: bool = False):
    last_agent = "chat"
    status     = None
    try:
        for ev in orch.run(query, mode=orch.thinking_mode):
            t = ev.type
            if t == "thinking":
                if ev.message == "Analyzing..." and not verbose:
                    status = console.status("[bold purple]🧠 Reasoning...[/]", spinner="dots")
                    status.start()
                elif verbose:
                    show_thinking(ev.message)
                else:
                    if status:
                        status.stop()
                        status = None
            elif t == "plan_display":
                if status:
                    status.stop()
                    status = None
                console.print(ev.message)
                # Plan confirmation is displayed; user continues conversation to confirm
            else:
                if status:
                    status.stop()
                    status = None
                if t == "agent_start":
                    last_agent = ev.agent
                    show_agent_event(ev.agent, t, ev.message)
                elif t in ("tool_call", "tool_result", "agent_progress"):
                    show_agent_event(ev.agent or last_agent, t, ev.message)
                elif t == "error":
                    show_agent_event(ev.agent or last_agent, "error", ev.message)
                elif t == "done" and ev.message:
                    show_answer(ev.message, agent=last_agent)
    finally:
        if status:
            status.stop()


def handle_command(
    orch: MasterOrchestrator, profile, cmd: str, verbose: bool = False
):
    parts = cmd.strip().split()
    base  = parts[0].lower()

    # ── Mode switching ────────────────────────────────────────────────────────
    if base == "/mode":
        if len(parts) < 2:
            _show_mode_status(orch.thinking_mode)
            console.print("  Usage: /mode fast | /mode think | /mode complex")
            return
        new_mode = parts[1].lower()
        if orch.set_mode(new_mode):
            label = MODE_LABELS.get(new_mode, new_mode)
            desc  = MODE_DESCRIPTIONS.get(new_mode, "")
            success_message(f"Switched to {label} — {desc}")
            console.print(f"  [dim]New session started.[/]")
        else:
            error_panel("INVALID MODE", f"Valid modes: fast, think, complex")

    # ── Agent switching ───────────────────────────────────────────────────────
    elif base == "/agent":
        if len(parts) < 2:
            console.print("  Usage: /agent finance | code | browser | research | chat")
            return
        agent_name = parts[1].lower()
        valid = {"finance", "code", "browser", "research", "chat"}
        if agent_name in valid:
            orch.set_agent(agent_name)
            success_message(f"Switched to {agent_name.capitalize()} Agent — new session started.")
        else:
            error_panel("INVALID AGENT", f"Valid agents: {', '.join(sorted(valid))}")

    # ── History ───────────────────────────────────────────────────────────────
    elif base == "/history":
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        info_panel(orch.session_store.format_history(limit))

    # ── Session info ──────────────────────────────────────────────────────────
    elif base == "/session":
        s = orch.session_store.current()
        name = s.name or f"Session {s.session_id}"
        info_panel(
            f"CURRENT SESSION\n\n"
            f"  Name   : {name}\n"
            f"  ID     : {s.session_id}\n"
            f"  Agent  : {s.active_agent}\n"
            f"  Mode   : {s.thinking_mode}\n"
            f"  Messages: {len(s.entries)}\n"
            f"  Started : {s.created_at[:16].replace('T', ' ')}"
        )

    # ── Help ─────────────────────────────────────────────────────────────────
    elif base == "/help":
        from rich.table import Table
        from rich.panel import Panel

        t = Table(show_header=True, header_style="bold #FFC107", border_style="dim")
        t.add_column("Command",     style="bold white")
        t.add_column("Description", style="dim white")
        for c, d in [
            ("/help",              "Show this help"),
            ("/mode fast|think|complex", "Switch thinking mode"),
            ("/agent <name>",      "Switch agent (finance|code|browser|research|chat)"),
            ("/agents",            "List all agents"),
            ("/history [n]",       "Show last N sessions (default 20)"),
            ("/session",           "Show current session info"),
            ("/models",            "Show LLM providers"),
            ("/memory",            "Memory stats"),
            ("/think <q>",         "Run thinking engine on query"),
            ("/profile",           "Show profile"),
            ("/reset",             "Reset session memory"),
            ("/desktop",           "Toggle desktop control (requires DESKTOP_ENABLED=true)"),
            ("/test",              "Run diagnostics"),
            ("/import-memory",     "Import memory from ChatGPT/Claude/Gemini"),
            ("/export-profile",    "Export your profile as JSON"),
            ("/uninstall",         "Remove all Lirox data from this device"),
            ("/update",            "Update Lirox to the latest version"),
            ("/exit",              "Shutdown"),
        ]:
            t.add_row(c, d)
        console.print(
            Panel(
                t,
                title=f"[bold #FFC107]LIROX v{APP_VERSION} — COMMANDS[/]",
                border_style="#FFC107",
            )
        )

    # ── Agents list ───────────────────────────────────────────────────────────
    elif base == "/agents":
        from rich.table import Table

        t = Table(show_header=True, header_style="bold #FFC107")
        t.add_column("Agent")
        t.add_column("Icon")
        t.add_column("Capability")
        t.add_column("Planning")
        for n, ic, d, p, c in [
            ("Finance",  "📊", "Markets, stocks, portfolios, valuation", "✓", "cyan"),
            ("Code",     "💻", "Write, debug, review, execute code + desktop", "✓", "green"),
            ("Browser",  "🌐", "Web navigation, content extraction, live data", "—", "orange1"),
            ("Research", "🔬", "Deep multi-source research (Perplexity-style)", "—", "medium_purple1"),
            ("Chat",     "💬", "General conversation (no planning mode)", "—", "yellow"),
        ]:
            t.add_row(f"[{c}]{n}[/]", ic, d, p)
        console.print(t)
        console.print()

    # ── Models ────────────────────────────────────────────────────────────────
    elif base == "/models":
        providers = available_providers()
        info_panel(
            "AVAILABLE LLM PROVIDERS\n\n"
            + ("\n".join(f"  ✓ {p}" for p in providers) if providers else "  None configured")
        )

    # ── Memory ────────────────────────────────────────────────────────────────
    elif base == "/memory":
        stats_lines = ["MEMORY STATS (per agent)\n"]
        for agent_type, mem in orch._agent_memory.items():
            s = mem.get_stats()
            stats_lines.append(
                f"  {agent_type.value:10}: {s['buffer_size']} msgs, {s['long_term_facts']} facts"
            )
        if not orch._agent_memory:
            stats_lines.append("  No agents activated yet.")
        global_s = orch.global_memory.get_stats()
        stats_lines.append(f"\n  Global memory: {global_s['buffer_size']} msgs")
        info_panel("\n".join(stats_lines))

    # ── Think ─────────────────────────────────────────────────────────────────
    elif base == "/think":
        q = cmd[7:].strip()
        if q:
            from lirox.thinking.chain_of_thought import ThinkingEngine
            show_thinking(ThinkingEngine().reason(q))
        else:
            info_panel("Usage: /think <question>")

    # ── Profile ───────────────────────────────────────────────────────────────
    elif base == "/profile":
        info_panel(f"PROFILE\n\n{profile.summary()}")

    # ── Reset ────────────────────────────────────────────────────────────────
    elif base == "/reset":
        if confirm_prompt("Reset all session memory?"):
            for mem in orch._agent_memory.values():
                mem.conversation_buffer.clear()
            orch.global_memory.conversation_buffer.clear()
            orch.session_store.new_session()
            success_message("Memory reset. New session started.")

    # ── Desktop ──────────────────────────────────────────────────────────────
    elif base == "/desktop":
        from lirox.config import DESKTOP_ENABLED
        if not DESKTOP_ENABLED:
            info_panel(
                "Desktop control is DISABLED.\n\n"
                "To enable:\n"
                "  1. Add DESKTOP_ENABLED=true to your .env\n"
                "  2. Install: pip install pyautogui pillow\n"
                "  3. macOS: grant Accessibility permissions in System Preferences\n"
                "  4. Restart Lirox"
            )
        else:
            try:
                from lirox.tools.desktop import take_screenshot, get_open_windows
                path    = take_screenshot()
                windows = get_open_windows()
                success_message(f"Desktop control ACTIVE\n  Screenshot: {path}\n  Open windows:\n{windows}")
            except Exception as e:
                error_panel("DESKTOP ERROR", str(e))

    # ── Test ─────────────────────────────────────────────────────────────────
    elif base == "/test":
        info_panel("Running diagnostics...")
        from lirox.config import DESKTOP_ENABLED
        for n, f in [
            ("Providers",      lambda: ", ".join(available_providers()) or "None"),
            ("Global Memory",  lambda: f"{orch.global_memory.get_stats()['buffer_size']} buffered"),
            ("Sessions",       lambda: f"{len(orch.session_store.list_sessions())} sessions stored"),
            ("Thinking Mode",  lambda: orch.thinking_mode),
            ("Desktop Ctrl",   lambda: "ENABLED" if DESKTOP_ENABLED else "disabled"),
            ("Version",        lambda: f"v{APP_VERSION}"),
            ("Agents",         lambda: "Finance, Code, Browser, Research, Chat"),
        ]:
            try:
                console.print(f"  [green]✓[/] {n:22}: {f()}")
            except Exception as e:
                console.print(f"  [red]✖[/] {n:22}: {e}")
        success_message("Diagnostics complete.")

    elif base in ("/uninstall", "/update", "/import-memory", "/export-profile"):
        # Keep existing implementations from v2.1 unchanged
        _legacy_commands(orch, profile, cmd, base)

    else:
        console.print(f"  [dim]Unknown command: {base}. Type /help for options.[/]")


def _legacy_commands(orch, profile, cmd, base):
    """Preserve existing /uninstall, /update, /import-memory, /export-profile from v2.1"""
    import shutil, subprocess
    from lirox.config import PROJECT_ROOT, DATA_DIR, OUTPUTS_DIR

    if base == "/uninstall":
        from rich.panel import Panel as _Panel
        console.print()
        console.print(_Panel(
            "[bold red]⚠️ UNINSTALL LIROX[/]\n\n"
            "This will remove all Lirox data from your device:\n"
            "  • Profile and settings\n"
            "  • Memory and learning data\n"
            "  • Configuration (.env)\n\n"
            "The Python package itself must be removed separately:\n"
            "  [bold]pip uninstall lirox[/]",
            border_style="red"
        ))
        if confirm_prompt("Delete ALL Lirox data? This cannot be undone."):
            for path in [
                os.path.join(PROJECT_ROOT, "profile.json"),
                os.path.join(PROJECT_ROOT, ".env"),
                os.path.join(PROJECT_ROOT, "skills_config.json"),
            ]:
                if os.path.exists(path):
                    os.remove(path)
            for dir_path in [DATA_DIR, OUTPUTS_DIR]:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
            success_message("All Lirox data deleted. Run 'pip uninstall lirox' to remove the package.")
            info_panel("Goodbye. 👋")
            sys.exit(0)

    elif base == "/update":
        info_panel("Checking for updates...")
        try:
            if os.path.exists(os.path.join(PROJECT_ROOT, ".git")):
                result = subprocess.run(
                    ["git", "-C", PROJECT_ROOT, "pull"],
                    capture_output=True, text=True, check=True
                )
                if "Already up to date." in result.stdout:
                    success_message("Lirox is already up to date.")
                else:
                    console.print(f"[dim]{result.stdout.strip()}[/]")
                    subprocess.run([sys.executable, "-m", "pip", "install", "-e", PROJECT_ROOT], capture_output=True)
                    success_message("Lirox updated. Please restart.")
            else:
                info_panel("Not a Git repo.\nRun: pip install --upgrade lirox")
        except Exception as e:
            error_panel("UPDATE FAILED", str(e))

    elif base == "/import-memory":
        from lirox.ui.wizard import _show_memory_import_prompt
        _show_memory_import_prompt(profile, profile.data.get("user_name", "User"),
                                   profile.data.get("agent_name", "Lirox"))

    elif base == "/export-profile":
        import json as _json
        console.print(_json.dumps(profile.data, indent=2, default=str))
