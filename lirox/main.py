"""Lirox v1.1 — Entry Point"""
import os
import sys
import time
import argparse
import re
from pathlib import Path

from lirox.utils.dependency_bootstrap import (
    required_package_map, missing_packages,
    install_missing_packages, manual_install_hint,
)

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def check_dependencies():
    package_to_module = required_package_map()
    missing = missing_packages(package_to_module)
    if not missing:
        return
    print(f"\n[Lirox] Missing dependencies: {', '.join(missing)}")
    print("[Lirox] Installing...")
    installed, failed = install_missing_packages(missing)
    if installed:
        print(f"[Lirox] Installed: {', '.join(installed)}")
    remaining = missing_packages(package_to_module)
    if not remaining:
        print("[Lirox] Done. Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    print(f"\n[!] Still missing: {', '.join(remaining)}")
    print(manual_install_hint(remaining))
    sys.exit(1)


def get_prompt_label(agent_name: str) -> list:
    return [("class:prompt", f"[{agent_name}] "), ("class:symbol", "✦ ")]


# Module-level storage for the last thinking session (used by /expand thinking)
_last_thinking: dict = {"steps": [], "complexity": "", "elapsed": 0.0, "query": "", "full_result": None}


def process_query(orch, query: str, verbose: bool = False):
    """
    Unified entry point for query processing.
    Uses MasterOrchestrator to ensure consistency.
    """
    from lirox.ui.display import (
        render_streaming_chunk, console, show_agent_event,
        show_thinking_phase, show_answer
    )
    
    _last_thinking["query"] = query
    _last_thinking["steps"] = []
    
    # Run through orchestrator
    try:
        last_event_type = None
        for event in orch.run(query):
            etype = event.type
            
            # ── Handle Thinking Phases ──
            if etype == "thinking_phase":
                show_thinking_phase(event.data)
            
            # ── Handle Agent Progress ──
            elif etype == "agent_progress":
                show_agent_event(event.message, agent=event.agent, etype=etype)
                _last_thinking["steps"].append(event.message)

            # ── Handle Tool Calls ──
            elif etype == "tool_call":
                show_agent_event(event.message, agent=event.agent, etype="tool_call")

            # ── Handle Tool Results ──
            elif etype == "tool_result":
                show_agent_event(event.message, agent=event.agent, etype="agent_progress")

            # ── Handle Warnings ──
            elif etype == "warning":
                console.print(f"  [bold #FFC107]⚠ {event.message}[/]")
                
            # ── Handle Streaming ──
            elif etype == "streaming":
                msg = event.data.get("message", "")
                render_streaming_chunk(msg)
                
            # ── Handle Done ──
            elif etype == "done":
                if last_event_type == "streaming":
                    console.print()  # Finish the streaming line
                    # Response already displayed via streaming — just show Done
                    console.print(f"  [bold #10b981]✓ Done[/]")
                else:
                    # Non-streamed response (e.g. filegen results) — render normally
                    show_answer(event.message)
                # Check if this is a thinking-done event with full data
                thinking_data = event.data.get("thinking_result")
                if thinking_data:
                    _last_thinking["full_result"] = thinking_data
                _last_thinking["elapsed"] = event.data.get("total_time", 0.0)
                
            # ── Handle Errors ──
            elif etype == "error":
                from lirox.ui.display import error_panel
                error_panel("ORCHESTRATOR ERROR", event.message)
                
            last_event_type = etype
            
    except Exception as e:
        from lirox.ui.display import error_panel
        error_panel("PROCESS ERROR", str(e))
        import logging
        logging.error(f"Error in process_query: {e}", exc_info=True)
    finally:
        # Auto-train after every successful query to update LearningsStore
        try:
            orch.record_interaction()
        except:
            pass


def handle_command(orch, profile, cmd: str, verbose: bool = False):
    from lirox.ui.display import (
        console, error_panel, info_panel, success_message, confirm_prompt,
    )
    from lirox.config import APP_VERSION

    parts = cmd.strip().split()
    base  = parts[0].lower()
    try:
        _handle(orch, profile, cmd, base, parts, verbose)
    except KeyboardInterrupt:
        console.print("\n  [dim]Interrupted.[/]")
    except Exception as e:
        error_panel("COMMAND ERROR", str(e))


def _handle(orch, profile, cmd, base, parts, verbose):
    from lirox.ui.display import (
        console, error_panel, info_panel, success_message, confirm_prompt,
    )
    from lirox.config import APP_VERSION
    from lirox.utils.llm import available_providers

    if base == "/help":
        from rich.table import Table as _T
        from rich.panel import Panel as _P
        t = _T(show_header=True, header_style="bold #FFC107", border_style="dim")
        t.add_column("Command", style="bold white")
        t.add_column("Description", style="dim white")
        rows = [
            ("/help",               "Show this help"),
            ("/setup",              "Re-run setup wizard"),
            ("/history [n]",        "Show last N sessions"),
            ("/session",            "Current session info"),
            ("/models",             "Available LLM providers"),
            ("/use-model <n>",      "Pin a provider (groq, gemini, openai…)"),
            ("/memory",             "Memory stats"),
            ("/profile",            "Show your profile"),
            ("/reset",              "Reset session memory"),
            ("/test",               "Run diagnostics"),
            ("/health",             "Run subsystem health checks"),
            ("/train",              "Auto-trains after each conversation (no action needed)"),
            ("/recall",             "Show everything Lirox knows about you"),
            ("/workspace [path]",   "Show or change workspace directory"),
            ("/expand thinking",    "Show detailed reasoning from last query"),
            ("/thinking-help",      "Thinking display controls and legend"),
            ("/backup",             "Backup all data"),
            ("/export-memory",      "Export profile + learnings as JSON"),
            ("/import-memory",      "Import from ChatGPT/Claude/Gemini/Lirox (paste or file)"),
            ("/restart",            "Restart Lirox"),
            ("/update",             "Update to latest version"),
            ("/uninstall",          "Remove all Lirox data"),
            ("/exit",               "Shutdown"),
        ]
        for c, d in rows: t.add_row(c, d)
        console.print(_P(t, title=f"[bold #FFC107]LIROX v{APP_VERSION} — COMMANDS[/]",
                          border_style="#FFC107"))

    elif base == "/setup":
        from lirox.ui.wizard import run_setup_wizard
        try:
            run_setup_wizard(profile)
            orch.profile_data = profile.data
            success_message("Setup complete!")
        except KeyboardInterrupt:
            console.print("\n  [dim]Setup cancelled.[/]")

    elif base == "/history":
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        info_panel(orch.session_store.format_history(limit))

    elif base == "/session":
        s = orch.session_store.current()
        info_panel(f"Session ID: {s.session_id}\nCreated: {s.created_at}\nEntries: {len(s.entries)}")

    elif base == "/models":
        avail = available_providers()
        lines = []
        for p in avail:
            if p == "ollama":
                m = os.getenv("OLLAMA_MODEL", "llama3")
                lines.append(f"• [bold green]ollama[/] (Local) -> [cyan]{m}[/]")
            elif p == "groq":
                lines.append(f"• [bold green]groq[/] (Cloud) -> [cyan]llama-3.3-70b-versatile[/]")
            elif p == "gemini":
                lines.append(f"• [bold green]gemini[/] (Cloud) -> [cyan]gemini-2.0-flash[/]")
            else:
                lines.append(f"• [bold green]{p}[/] (Cloud)")
        
        if not avail:
            info_panel("No providers configured. Run /setup to add one.")
        else:
            info_panel("Active LLM Providers:\n" + "\n".join(lines))

    elif base == "/use-model":
        if len(parts) < 2:
            error_panel("USAGE", "/use-model <provider_name>")
            return
        p = parts[1].lower()
        avail = available_providers()
        if p not in avail:
            error_panel("INVALID", f"'{p}' not in {avail}")
            return
        profile.data["llm_provider"] = p
        profile.save()
        # Actually set the env var that generate_response() reads
        os.environ["_LIROX_PINNED_MODEL"] = p
        
        msg = f"LLM provider pinned to: [bold cyan]{p}[/]"
        if p == "ollama":
            msg += f"\nLocal model: [bold cyan]{os.getenv('OLLAMA_MODEL', 'llama3')}[/]"
        success_message(msg)

    elif base == "/memory":
        from lirox.learning.manager import LearningManager
        lm = LearningManager()
        stats = lm.stats()
        text = "\n".join(f"{k.capitalize()}: {v}" for k, v in stats.items())
        info_panel(text)

    elif base == "/profile":
        info_panel(str(profile.data))

    elif base == "/reset":
        if confirm_prompt("Clear current session history?"):
            orch.session_store.reset()
            success_message("Session reset.")

    elif base == "/test":
        from lirox.core.diagnostics import run_diagnostics
        run_diagnostics()

    elif base == "/health":
        from lirox.core.health import run_health_checks
        report = run_health_checks()
        for check in report.checks:
            status = "✓" if check.ok else "✗"
            color = "green" if check.ok else "red"
            console.print(f"  [{color}]{status}[/{color}] {check.name}: {check.message}")

    elif base == "/train":
        info_panel("Training now happens automatically in background after each conversation.\nNo manual /train needed.")

    elif base == "/recall":
        from lirox.learning.manager import LearningManager
        lm = LearningManager()
        facts = lm.recall_facts(limit=10)
        if not facts:
            info_panel("I don't know much yet. Let's talk more!")
        else:
            info_panel("Here's what I've learned about you:\n\n- " + "\n- ".join(facts))

    elif base == "/workspace":
        if len(parts) > 1:
            new_path = parts[1]
            os.environ["LIROX_WORKSPACE"] = new_path
            success_message(f"Workspace set to: {new_path}")
        else:
            info_panel(f"Current Workspace: {os.getenv('LIROX_WORKSPACE', str(Path.home() / 'Desktop'))}")

    elif base == "/expand":
        if len(parts) > 1 and parts[1] == "thinking":
            if not _last_thinking["steps"] and not _last_thinking.get("full_result"):
                error_panel("NO DATA", "No recent thinking trace to expand.")
                return
            from lirox.ui.display import show_thinking
            show_thinking(
                _last_thinking["query"],
                _last_thinking["steps"],
                _last_thinking["elapsed"],
                full_result=_last_thinking.get("full_result"),
            )
        else:
            error_panel("USAGE", "/expand thinking")

    elif base == "/thinking-help":
        from lirox.ui.thinking_controls import ThinkingControls
        ThinkingControls.show_help()

    elif base == "/backup":
        from lirox.core.backup import create_backup
        path = create_backup()
        success_message(f"Backup created: {path}")

    elif base == "/export-memory":
        from lirox.learning.exporter import export_learnings
        path = export_learnings()
        success_message(f"Memory exported to: {path}")

    elif base == "/import-memory":
        if len(parts) >= 2:
            # Non-interactive file import
            from lirox.learning.importer import import_learnings
            res = import_learnings(parts[1])
            success_message(f"Imported {res['facts']} facts and {res['prefs']} preferences.")
        else:
            # Interactive mode (paste or file picker)
            from lirox.learning.importer import import_memory_interactive
            if import_memory_interactive():
                success_message("Memory imported successfully")

    elif base == "/restart":
        success_message("Restarting Lirox...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    elif base == "/update":
        from lirox.core.updater import run_update
        run_update()

    elif base == "/uninstall":
        if confirm_prompt("ARE YOU SURE? This will delete ALL data and remove Lirox from your device."):
            from lirox.config import delete_all_data
            delete_all_data()
            sys.exit(0)

    else:
        error_panel("UNKNOWN COMMAND", f"Type /help for a list of commands.")


def main():
    """Main CLI entry point with production-grade error handling."""
    try:
        # ── Bootstrap FIRST ──
        check_dependencies()

        from lirox.core.logger import configure_logging
        configure_logging()

        from lirox.config import ensure_directories
        ensure_directories()

        from lirox.orchestrator.master import MasterOrchestrator
        from lirox.ui.display import show_welcome, show_status_card, console, error_panel
        from lirox.utils.llm import available_providers
        from lirox.config import APP_VERSION
        from lirox.agent.profile import UserProfile

        parser = argparse.ArgumentParser(description=f"Lirox v{APP_VERSION}")
        parser.add_argument("--setup",   action="store_true", help="Run setup wizard")
        parser.add_argument("--version", action="store_true", help="Show version")
        parser.add_argument("--verbose", action="store_true", help="Show thinking traces")
        
        # Handle command line shortcuts
        if len(sys.argv) > 1 and sys.argv[1] == "setup":
            sys.argv[1] = "--setup"

        args = parser.parse_args()

        if args.version:
            print(f"Lirox v{APP_VERSION}"); sys.exit(0)

        profile      = UserProfile()
        orchestrator = MasterOrchestrator(profile_data=profile.data)

        # Restore pinned LLM provider from profile (persists across restarts)
        _saved_provider = profile.data.get("llm_provider", "")
        if _saved_provider and _saved_provider != "auto":
            os.environ["_LIROX_PINNED_MODEL"] = _saved_provider

        show_welcome()

        if not profile.is_setup() or args.setup:
            from lirox.ui.wizard import run_setup_wizard
            try:
                run_setup_wizard(profile)
                orchestrator.profile_data = profile.data
                
                # Re-pin model if it was set during setup
                _new_provider = profile.data.get("llm_provider", "")
                if _new_provider and _new_provider != "auto":
                    os.environ["_LIROX_PINNED_MODEL"] = _new_provider
            except KeyboardInterrupt:
                console.print("\n  [dim]Setup skipped.[/]")

        show_status_card(profile.data, available_providers())
        console.print(f"  [dim]Workspace: {os.getenv('LIROX_WORKSPACE', str(Path.home() / 'Desktop'))}[/]")
        console.print("  [dim]Type /help for commands  ·  /setup to configure[/]\n")

        from prompt_toolkit import PromptSession
        from prompt_toolkit.styles import Style
        from prompt_toolkit.completion import Completer, Completion

        cmd_docs = {
            "/help":            "Show all commands",
            "/setup":           "Re-run setup wizard",
            "/history":         "View past conversations",
            "/session":         "Current session details",
            "/models":          "List available AI providers",
            "/use-model":       "Switch default AI provider",
            "/memory":          "Show learning statistics",
            "/profile":         "View user profile",
            "/reset":           "Clear current session",
            "/test":            "Run quick diagnostics",
            "/health":          "Deep subsystem health checks",
            "/train":           "Auto-trains in background (no action needed)",
            "/recall":          "Show learned facts about you",
            "/workspace":       "Set active directory",
            "/expand thinking": "View last reasoning trace",
            "/thinking-help":  "Thinking display controls and legend",
            "/backup":          "Create a full data backup",
            "/export-memory":   "Save learnings to JSON",
            "/import-memory":   "Import external learnings (paste or file)",
            "/restart":         "Reload Lirox",
            "/update":          "Check for updates",
            "/uninstall":       "Delete all Lirox data",
            "/exit":            "Shutdown",
        }

        class SlashCompleter(Completer):
            def get_completions(self, document, complete_event):
                text = document.text_before_cursor.lstrip()
                if not text.startswith("/"): return
                for cmd, desc in cmd_docs.items():
                    if cmd.startswith(text.lower()):
                        yield Completion(cmd, start_position=-len(text), display_meta=desc)

        session = PromptSession(completer=SlashCompleter(), complete_while_typing=True)
        style   = Style.from_dict({"prompt": "ansiyellow bold", "symbol": "ansiyellow"})

        # Main REPL Loop
        while True:
            try:
                line = session.prompt(
                    get_prompt_label(profile.data.get("agent_name", "Lirox")),
                    style=style
                ).strip()
                
                if not line:
                    continue
                    
                if line.lower() in ("exit", "quit", "/exit"):
                    from lirox.ui.display import info_panel
                    info_panel("Shutting down. Goodbye."); break
                    
                if line.startswith("/"):
                    handle_command(orchestrator, profile, line, verbose=args.verbose)
                    continue
                    
                process_query(orchestrator, line, verbose=args.verbose)
                
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted. Type /exit to quit.[/]")
                continue 
            except EOFError:
                break
            except Exception as e:
                error_panel("FATAL LOOP ERROR", f"An unexpected error occurred: {e}")
                import logging
                logging.error(f"REPL Fatal Error: {e}", exc_info=True)

    except Exception as fatal:
        print(f"\n[bold red]CRITICAL FAILURE:[/bold red] {fatal}")
        import logging
        logging.critical(f"Main Entry Point Failure: {fatal}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
