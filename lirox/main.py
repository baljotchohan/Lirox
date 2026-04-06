"""Lirox — Multi-Agent Entry Point"""
import os
import sys
import time
import argparse


def check_dependencies():
    required = {
        "rich":           "rich",
        "prompt_toolkit": "prompt-toolkit",
        "psutil":         "psutil",
        "dotenv":         "python-dotenv",
        "bs4":            "beautifulsoup4",
        "lxml":           "lxml",
        "requests":       "requests",
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
from lirox.config import APP_VERSION


def get_prompt_label(agent_name: str) -> list:
    return [
        ('class:prompt',  f"[{agent_name}] "),
        ('class:symbol',  "✦ "),
    ]


def main():
    check_dependencies()

    parser = argparse.ArgumentParser(description="Lirox — Multi-Agent AI Kernel")
    parser.add_argument("--setup",   action="store_true", help="Run setup wizard")
    parser.add_argument("--verbose", action="store_true", help="Show thinking traces in terminal")
    args = parser.parse_args()

    from lirox.agent.profile import UserProfile
    profile      = UserProfile()
    orchestrator = MasterOrchestrator(profile_data=profile.data)

    show_welcome()

    if not profile.is_setup() or args.setup:
        from lirox.ui.wizard import run_setup_wizard
        try:
            run_setup_wizard(profile)
        except KeyboardInterrupt:
            console.print("\n  [dim]Setup skipped.[/]")

    show_status_card(profile.data, available_providers())
    console.print("  [dim]Thinking: always-on complex mode  ·  /help for commands[/]\n")

    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.completion import Completer, Completion

    agent_name = profile.data.get("agent_name", "Lirox")
    last_int   = 0.0

    style = Style.from_dict({
        'prompt': 'ansiyellow bold',
        'symbol': 'ansiyellow',
    })

    commands = [
        "/help",
        "/agent finance", "/agent code", "/agent browser", "/agent research", "/agent chat",
        "/agents", "/history", "/session", "/models", "/memory", "/think", "/profile",
        "/reset", "/desktop", "/test", "/import-memory", "/export-profile",
        "/uninstall", "/update", "/exit",
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
            prompt_label = get_prompt_label(agent_name)
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


def process_query(orch: MasterOrchestrator, query: str, verbose: bool = False):
    last_agent = "chat"
    status     = None
    try:
        for ev in orch.run(query):
            t = ev.type
            if t == "thinking":
                if ev.message == "Analyzing..." and not verbose:
                    if status is None:
                        status = console.status("[bold purple]🧠 Thinking...[/]", spinner="dots")
                        status.start()
                elif verbose:
                    if status:
                        status.stop()
                        status = None
                    show_thinking(ev.message)
                else:
                    # Non-verbose: stop spinner on first real thinking chunk
                    if ev.message != "Analyzing..." and status:
                        status.stop()
                        status = None
            elif t == "plan_display":
                if status:
                    status.stop()
                    status = None
                console.print(ev.message)
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

    # ── Agent switching ───────────────────────────────────────────────────────
    if base == "/agent":
        if len(parts) < 2:
            console.print("  Usage: /agent finance | code | browser | research | chat")
            return
        agent_name = parts[1].lower()
        valid = {"finance", "code", "browser", "research", "chat"}
        if agent_name in valid:
            orch.set_agent(agent_name)
            success_message(f"Switched to {agent_name.capitalize()} Agent — new session started.")
            if agent_name != "chat":
                agent = orch._get_agent(orch.session_store.current().active_agent
                                        and __import__('lirox.orchestrator.master', fromlist=['AgentType']).AgentType(agent_name))
                if agent and hasattr(agent, 'get_onboarding_message'):
                    console.print(f"\n  {agent.get_onboarding_message()}\n")
        else:
            error_panel("INVALID AGENT", f"Valid agents: {', '.join(sorted(valid))}")

    # ── History ───────────────────────────────────────────────────────────────
    elif base == "/history":
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        info_panel(orch.session_store.format_history(limit))

    # ── Session info ──────────────────────────────────────────────────────────
    elif base == "/session":
        s    = orch.session_store.current()
        name = s.name or f"Session {s.session_id}"
        info_panel(
            f"CURRENT SESSION\n\n"
            f"  Name    : {name}\n"
            f"  ID      : {s.session_id}\n"
            f"  Agent   : {s.active_agent}\n"
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
            ("/help",               "Show this help"),
            ("/agent <name>",       "Switch agent (finance|code|browser|research|chat)"),
            ("/agents",             "List all agents"),
            ("/history [n]",        "Show last N sessions (default 20)"),
            ("/session",            "Show current session info"),
            ("/models",             "Show LLM providers"),
            ("/memory",             "Memory stats"),
            ("/think <q>",          "Run thinking engine on query"),
            ("/profile",            "Show profile"),
            ("/reset",              "Reset session memory"),
            ("/desktop",            "Desktop control status"),
            ("/test",               "Run diagnostics"),
            ("/import-memory",      "Import memory from ChatGPT/Claude/Gemini"),
            ("/export-profile",     "Export your profile as JSON"),
            ("/uninstall",          "Remove all Lirox data from this device"),
            ("/update",             "Update Lirox to the latest version"),
            ("/exit",               "Shutdown"),
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
        t.add_column("Pipeline")
        for n, ic, d, p, c in [
            ("Finance",  "📊", "Markets, stocks, portfolios, valuation",          "5-stage", "cyan"),
            ("Code",     "💻", "Write, debug, review, execute code + desktop",    "11-stage", "green"),
            ("Browser",  "🌐", "Web navigation, content extraction, live data",   "Direct",  "orange1"),
            ("Research", "🔬", "Deep multi-source research (Perplexity-style)",   "5-stage", "medium_purple1"),
        ]:
            t.add_row(f"[{c}]{n}[/]", ic, d, p)
        console.print(t)
        console.print(
            "\n  [dim]Thinking: Always-on complex mode for all agents[/]\n"
        )

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
                f"  {agent_type.value:10}: {s['buffer_size']} msgs, {s.get('long_term_facts', 0)} facts"
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
                "  2. Install: pip install pyautogui pillow pytesseract\n"
                "  3. macOS: grant Accessibility in System Settings → Privacy → Accessibility\n"
                "  4. Restart Lirox"
            )
        else:
            try:
                from lirox.tools.desktop import take_screenshot, get_open_windows
                path    = take_screenshot()
                windows = get_open_windows()
                success_message(f"Desktop control ACTIVE\n  Screenshot: {path}\n  Windows:\n{windows}")
            except Exception as e:
                error_panel("DESKTOP ERROR", str(e))

    # ── Test ─────────────────────────────────────────────────────────────────
    elif base == "/test":
        info_panel("Running diagnostics...")
        from lirox.config import DESKTOP_ENABLED
        for n, f in [
            ("Providers",     lambda: ", ".join(available_providers()) or "None"),
            ("Global Memory", lambda: f"{orch.global_memory.get_stats()['buffer_size']} buffered"),
            ("Sessions",      lambda: f"{len(orch.session_store.list_sessions())} sessions stored"),
            ("Thinking",      lambda: "Always-on complex mode"),
            ("Desktop Ctrl",  lambda: "ENABLED" if DESKTOP_ENABLED else "disabled"),
            ("Version",       lambda: f"v{APP_VERSION}"),
            ("Agents",        lambda: "Finance (5-stage) · Code (11-stage) · Browser · Research (5-stage)"),
        ]:
            try:
                console.print(f"  [green]✓[/] {n:22}: {f()}")
            except Exception as e:
                console.print(f"  [red]✖[/] {n:22}: {e}")
        success_message("Diagnostics complete.")

    elif base in ("/uninstall", "/update", "/import-memory", "/export-profile"):
        _legacy_commands(orch, profile, cmd, base)

    else:
        console.print(f"  [dim]Unknown command: {base}. Type /help for options.[/]")


def _legacy_commands(orch, profile, cmd, base):
    import shutil, subprocess
    from lirox.config import PROJECT_ROOT, DATA_DIR, OUTPUTS_DIR

    if base == "/uninstall":
        from rich.panel import Panel as _Panel
        console.print()
        console.print(_Panel(
            "[bold red]⚠️ UNINSTALL LIROX[/]\n\n"
            "This will remove all Lirox data:\n"
            "  • Profile and settings\n"
            "  • Memory and learning data\n"
            "  • Configuration (.env)\n\n"
            "Package: run 'pip uninstall lirox' separately.",
            border_style="red"
        ))
        if confirm_prompt("Delete ALL Lirox data? This cannot be undone."):
            for path in [
                os.path.join(PROJECT_ROOT, "profile.json"),
                os.path.join(PROJECT_ROOT, ".env"),
            ]:
                if os.path.exists(path):
                    os.remove(path)
            for dir_path in [DATA_DIR, OUTPUTS_DIR]:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
            success_message("All data deleted. Run 'pip uninstall lirox' to remove the package.")
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
                    subprocess.run([sys.executable, "-m", "pip", "install", "-e", PROJECT_ROOT],
                                   capture_output=True)
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
