"""Lirox v1.0.0 — Mind Agent Entry Point"""
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
    show_welcome, show_status_card, show_thinking, show_agent_event,
    show_answer, error_panel, info_panel, success_message,
    confirm_prompt, show_desktop_locked, console,
)
from lirox.utils.llm import available_providers
from lirox.config import APP_VERSION


def get_prompt_label(agent_name: str) -> list:
    return [
        ("class:prompt", f"[{agent_name}] "),
        ("class:symbol", "✦ "),
    ]


def main():
    check_dependencies()

    parser = argparse.ArgumentParser(description="Lirox v1.0.0 — Personal AI Agent")
    parser.add_argument("--setup",   action="store_true", help="Run setup wizard")
    parser.add_argument("--update",  action="store_true", help="Update Lirox")
    parser.add_argument("--verbose", action="store_true", help="Show thinking traces")
    args = parser.parse_args()

    if args.update:
        run_update()
        sys.exit(0)

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
    console.print("  [dim]Always-on deep thinking  ·  /help for commands[/]\n")

    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.completion import Completer, Completion

    agent_name = profile.data.get("agent_name", "Lirox")
    last_int   = 0.0

    style = Style.from_dict({
        "prompt": "ansiyellow bold",
        "symbol": "ansiyellow",
    })

    commands = [
        "/help", "/history", "/session", "/models", "/memory", "/think",
        "/profile", "/reset", "/desktop", "/test", "/pause", "/resume",
        "/train", "/learnings", "/add-skill", "/skills", "/add-agent", "/agents",
        "/improve", "/soul", "/mind", "/restart", "/screen", "/freeze",
        "/import-memory", "/export-profile", "/uninstall", "/update", "/exit",
    ]

    class SlashCommandCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor.lstrip()
            if not text.startswith("/"):
                return
            for cmd in commands:
                if cmd.startswith(text.lower()):
                    yield Completion(cmd, start_position=-len(text))

    session = PromptSession(
        completer=SlashCommandCompleter(), complete_while_typing=True
    )

    while True:
        try:
            # ── Block input during desktop control ────────────────────────────
            from lirox.tools.desktop import is_agent_locked
            if is_agent_locked():
                show_desktop_locked()
                time.sleep(0.5)
                continue

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
            # If agent is running, treat Ctrl+C as pause
            from lirox.tools.desktop import is_agent_locked, request_pause
            if is_agent_locked():
                request_pause()
                console.print("\n  [yellow]⏸  Pause requested. Agent will stop after current step.[/]")
                continue

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
    last_agent = "personal"
    status     = None
    try:
        for ev in orch.run(query):
            t = ev.type
            if t == "thinking":
                if ev.message == "Analyzing…" and not verbose:
                    if status is None:
                        status = console.status(
                            "[bold purple]🧠 Thinking…[/]", spinner="dots"
                        )
                        status.start()
                elif verbose:
                    if status:
                        status.stop()
                        status = None
                    show_thinking(ev.message)
                else:
                    if ev.message != "Analyzing…" and status:
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
                    last_agent = ev.agent or last_agent
                    show_agent_event(ev.agent, t, ev.message)
                elif t in ("tool_call", "tool_result", "agent_progress", "paused"):
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

    # ── Pause / Resume ────────────────────────────────────────────────────────
    if base == "/pause":
        from lirox.tools.desktop import request_pause, is_agent_locked
        if is_agent_locked():
            request_pause()
            console.print("  [yellow]⏸  Pause requested. Agent will stop after current step.[/]")
        else:
            console.print("  [dim]No agent running.[/]")

    elif base == "/resume":
        from lirox.tools.desktop import clear_pause, is_agent_locked
        if is_agent_locked():
            clear_pause()
            console.print("  [green]▶  Resumed.[/]")
        else:
            console.print("  [dim]No agent paused.[/]")

    # ── Help ──────────────────────────────────────────────────────────────────
    elif base == "/help":
        from rich.table import Table as _Table
        from rich.panel import Panel as _Panel
        t = _Table(show_header=True, header_style="bold #FFC107", border_style="dim")
        t.add_column("Command",     style="bold white")
        t.add_column("Description", style="dim white")
        for c, d in [
            ("/help",            "Show this help"),
            ("/history [n]",     "Show last N sessions (default 20)"),
            ("/session",         "Current session info"),
            ("/models",          "Available LLM providers"),
            ("/memory",          "Memory stats"),
            ("/think <q>",       "Run thinking engine on query"),
            ("/profile",         "Show your profile"),
            ("/reset",           "Reset session memory"),
            ("/desktop",         "Desktop control status + setup guide"),
            ("/pause",           "Pause agent while it controls the desktop"),
            ("/resume",          "Resume a paused agent"),
            ("/test",            "Run diagnostics"),
            ("/train",           "Train Mind Agent on recent sessions"),
            ("/learnings",       "View Mind Agent's user knowledge"),
            ("/add-skill <desc>","Generate a new skill via LLM"),
            ("/skills",          "List available skills"),
            ("/add-agent <desc>","Generate a new sub-agent via LLM"),
            ("/agents",          "List available sub-agents"),
            ("/improve",         "Run AI code improver on Lirox"),
            ("/soul",            "View Mind Agent's soul"),
            ("/mind",            "View full Mind Agent state"),
            ("/restart",         "Restart Lirox"),
            ("/screen [task]",   "Start screen mirroring with agent desktop control"),
            ("/freeze",          "Freeze desktop for agent control"),
            ("/import-memory",   "Import memory from ChatGPT/Claude/Gemini"),
            ("/export-profile",  "Export profile as JSON"),
            ("/uninstall",       "Remove all Lirox data"),
            ("/update",          "Update Lirox"),
            ("/exit",            "Shutdown"),
        ]:
            t.add_row(c, d)
        console.print(
            _Panel(
                t,
                title=f"[bold #FFC107]LIROX v{APP_VERSION} — COMMANDS[/]",
                border_style="#FFC107",
            )
        )

    # ── History ───────────────────────────────────────────────────────────────
    elif base == "/history":
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        info_panel(orch.session_store.format_history(limit))

    # ── Session ───────────────────────────────────────────────────────────────
    elif base == "/session":
        s    = orch.session_store.current()
        name = s.name or f"Session {s.session_id}"
        info_panel(
            f"CURRENT SESSION\n\n"
            f"  Name    : {name}\n"
            f"  ID      : {s.session_id}\n"
            f"  Agent   : personal\n"
            f"  Messages: {len(s.entries)}\n"
            f"  Started : {s.created_at[:16].replace('T', ' ')}"
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
        lines = ["MEMORY STATS\n"]
        for at, mem in orch._agent_memory.items():
            s = mem.get_stats()
            lines.append(
                f"  {at.value:12}: {s['buffer_size']} msgs, "
                f"{s.get('long_term_facts', 0)} facts"
            )
        if not orch._agent_memory:
            lines.append("  Agent not yet activated.")
        gs = orch.global_memory.get_stats()
        lines.append(f"\n  Global memory: {gs['buffer_size']} msgs")
        info_panel("\n".join(lines))

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

    # ── Reset ─────────────────────────────────────────────────────────────────
    elif base == "/reset":
        if confirm_prompt("Reset all session memory?"):
            for mem in orch._agent_memory.values():
                mem.conversation_buffer.clear()
            orch.global_memory.conversation_buffer.clear()
            orch.session_store.new_session()
            success_message("Memory reset. New session started.")

    # ── Desktop ───────────────────────────────────────────────────────────────
    elif base == "/desktop":
        from lirox.config import DESKTOP_ENABLED
        if not DESKTOP_ENABLED:
            info_panel(
                "Desktop control is DISABLED.\n\n"
                "To enable:\n"
                "  1. Add DESKTOP_ENABLED=true to your .env\n"
                "  2. pip install pyautogui pillow pytesseract\n"
                "  3. macOS: System Settings → Privacy → Accessibility → grant Terminal\n"
                "  4. Linux: sudo apt install scrot xdotool tesseract-ocr\n"
                "  5. Restart Lirox"
            )
        else:
            try:
                from lirox.tools.desktop import take_screenshot, get_open_windows
                path    = take_screenshot()
                windows = get_open_windows()
                success_message(
                    f"Desktop control ACTIVE\n"
                    f"  Screenshot: {path}\n"
                    f"  Windows:\n{windows}"
                )
            except Exception as e:
                error_panel("DESKTOP ERROR", str(e))

    # ── Test / Diagnostics ────────────────────────────────────────────────────
    elif base == "/test":
        info_panel("Running diagnostics…")
        from lirox.config import DESKTOP_ENABLED
        tests = [
            ("Providers",    lambda: ", ".join(available_providers()) or "None"),
            ("Global Memory",lambda: f"{orch.global_memory.get_stats()['buffer_size']} buffered"),
            ("Sessions",     lambda: f"{len(orch.session_store.list_sessions())} sessions"),
            ("Thinking",     lambda: "Always-on complex mode"),
            ("Desktop Ctrl", lambda: "ENABLED" if DESKTOP_ENABLED else "disabled"),
            ("Version",      lambda: f"v{APP_VERSION}"),
            ("Architecture", lambda: "Mind Agent + Personal Agent OS"),
        ]
        for name, fn in tests:
            try:
                console.print(f"  [green]✓[/] {name:22}: {fn()}")
            except Exception as e:
                console.print(f"  [red]✖[/] {name:22}: {e}")
        success_message("Diagnostics complete.")

    # ── LIROX V4.0 MIND COMMANDS ──────────────────────────────────────────────
    elif base == "/train":
        info_panel("Training Engine activated...")
        from lirox.mind.agent import get_trainer
        t = get_trainer(orch.global_memory)
        stats = t.train(orch.global_memory, orch.session_store)
        success_message(
            f"Training complete!\n"
            f"  Sessions analyzed: {stats['sessions_analyzed']}\n"
            f"  New facts: {stats['facts_added']}\n"
            f"  Topics updated: {stats['topics_updated']}\n"
            f"  Projects tracked: {stats['projects_added']}"
        )

    elif base == "/learnings":
        from lirox.mind.agent import get_learnings
        learn = get_learnings()
        info_panel(f"🧠 LEARNINGS STORE\n\n{learn.to_context_string()}")

    elif base == "/soul":
        from lirox.mind.agent import get_soul
        soul = get_soul()
        info_panel(f"👻 LIVING SOUL\n\n{soul.display_summary()}")

    elif base == "/mind":
        from lirox.mind.agent import get_soul, get_learnings, get_skills, get_sub_agents
        soul = get_soul()
        learnings_stats = get_learnings().stats_summary()
        sk = len(get_skills().list_skills())
        sa = len(get_sub_agents().list_agents())
        info_panel(
            f"🧠 MIND AGENT STATE\n\n"
            f"  Identity : {soul.get_name()}\n"
            f"  Nature   : {soul.state['personality'].get('core', '')[:60]}...\n\n"
            f"  Knowledge: {learnings_stats}\n"
            f"  Skills   : {sk} loaded\n"
            f"  Agents   : {sa} loaded\n"
            f"  Age      : {soul.state.get('interaction_count', 0)} interactions"
        )

    elif base == "/improve":
        info_panel("Self-Improver running... (this takes a minute)")
        from lirox.mind.agent import get_improver
        imp = get_improver()
        res = imp.improve()
        if res["improvements"]:
            fixes = "\n".join(f"  • {i['file']}: {i.get('fix', i.get('error', ''))}" for i in res["improvements"])
        else:
            fixes = "  None needed right now."
        success_message(
            f"Improvement cycle complete.\n"
            f"  Files audited: {res['files_audited']}\n"
            f"  Issues found: {res['issues_found']}\n"
            f"  Patches applied: {res['patches_applied']}\n\n"
            f"Patches:\n{fixes}"
        )
        from rich.markdown import Markdown
        sugg = imp.suggest_improvements()
        console.print(Markdown("### Improvement Suggestions\n" + sugg))

    elif base == "/add-skill":
        desc = cmd[10:].strip()
        if not desc:
            info_panel("Usage: /add-skill <description of what the skill should do>")
        else:
            info_panel("Building new skill via LLM...")
            from lirox.mind.agent import get_skills
            reg = get_skills()
            try:
                res = reg.build_skill_from_description(desc)
                name = res.get("name", "Unknown")
                success_message(f"Skill '{name}' created successfully!")
            except Exception as e:
                error_panel("SKILL GENERATION ERROR", str(e))

    elif base == "/skills":
        from lirox.mind.agent import get_skills
        reg = get_skills()
        skills = reg.list_skills()
        if not skills:
            info_panel("No skills loaded. Use /add-skill to create one.")
        else:
            lines = ["LOADED SKILLS\n"]
            for s in skills:
                lines.append(f"  • {s['name']}: {s['description']}")
            info_panel("\n".join(lines))

    elif base == "/add-agent":
        desc = cmd[10:].strip()
        if not desc:
            info_panel("Usage: /add-agent <description of the agent and what it does>")
        else:
            info_panel("Building new sub-agent via LLM...")
            from lirox.mind.agent import get_sub_agents
            reg = get_sub_agents()
            try:
                res = reg.build_agent_from_description(desc, name="NewAgent")
                name = res.get("name", "NewAgent")
                success_message(f"Agent '{name}' created successfully!")
            except Exception as e:
                error_panel("AGENT GENERATION ERROR", str(e))

    elif base == "/agents":
        from lirox.mind.agent import get_sub_agents
        reg = get_sub_agents()
        agents = reg.list_agents()
        if not agents:
            info_panel("No sub-agents loaded. Use /add-agent to create one.")
        else:
            lines = ["LOADED SUB-AGENTS\n"]
            for a in agents:
                lines.append(f"  • {a['name']}: {a['description']} (Role: {a['role']})")
            info_panel("\n".join(lines))

    # ── New v1.0.0 commands ───────────────────────────────────────────────────
    elif base == "/restart":
        info_panel("🔄 Restarting Lirox...")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    elif base == "/screen":
        task = cmd[7:].strip() or "Desktop control active"
        from lirox.tools.screen_mirror import ScreenMirror
        mirror = ScreenMirror()
        result = mirror.start_mirroring(task)
        console.print("[cyan]📺 Screen mirroring active - User input frozen[/]")
        console.print("[dim]Agent has full desktop control[/]")

    elif base == "/freeze":
        console.print("[bold cyan]🔒 DESKTOP FROZEN[/]")
        console.print("[dim]Agent controls desktop. Press ESC to stop.[/]")

    # ── Legacy commands ───────────────────────────────────────────────────────
    elif base in ("/uninstall", "/update", "/import-memory", "/export-profile"):
        _legacy_commands(orch, profile, cmd, base)

    else:
        console.print(f"  [dim]Unknown command: {base}. Type /help for options.[/]")


def run_update():
    import subprocess
    from lirox.config import PROJECT_ROOT
    info_panel("Checking for updates…")
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
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-e", PROJECT_ROOT],
                    capture_output=True
                )
                success_message("Lirox updated. Please restart.")
        else:
            info_panel("Not a Git repo.\nRun: pip install --upgrade lirox")
    except Exception as e:
        error_panel("UPDATE FAILED", str(e))


def _legacy_commands(orch, profile, cmd, base):
    import shutil
    from lirox.config import PROJECT_ROOT, DATA_DIR, OUTPUTS_DIR
    from rich.panel import Panel as _Panel
    from lirox.ui.display import info_panel, success_message, error_panel

    if base == "/uninstall":
        console.print()
        console.print(_Panel(
            "[bold red]⚠️  UNINSTALL LIROX[/]\n\n"
            "This removes ALL Lirox data:\n"
            "  • Profile and settings\n"
            "  • Memory and learning data\n"
            "  • Configuration (.env)\n\n"
            "Package: run 'pip uninstall lirox' separately.",
            border_style="red"
        ))
        if confirm_prompt("Delete ALL Lirox data? Cannot be undone."):
            for path in [
                os.path.join(PROJECT_ROOT, "profile.json"),
                os.path.join(PROJECT_ROOT, ".env"),
            ]:
                if os.path.exists(path):
                    os.remove(path)
            for dp in [DATA_DIR, OUTPUTS_DIR]:
                if os.path.exists(dp):
                    shutil.rmtree(dp, ignore_errors=True)
            success_message("All data deleted.")
            sys.exit(0)

    elif base == "/update":
        run_update()

    elif base == "/import-memory":
        console.print("\n  [bold #FFC107]To import memory from a file (Conversations JSON, txt, md):[/]")
        filepath = console.input("  [dim]Path to export file: [/]").strip()
        if filepath:
            from lirox.memory.import_handler import MemoryImporter
            from lirox.mind.agent import get_learnings
            info_panel("Importing memory...")
            res = MemoryImporter(get_learnings()).import_file(filepath)
            if "error" in res:
                error_panel("IMPORT ERROR", res["error"])
            else:
                success_message(
                    f"Import successful!\n"
                    f"  Source: {res['source']}\n"
                    f"  Imported: {res['imported']} messages\n"
                    f"  Facts added: {res['facts_added']}\n"
                    f"  Topics updated: {res['topics_added']}\n"
                    f"  Projects found: {res.get('projects_added', 0)}"
                )

    elif base == "/export-profile":
        import json as _json
        console.print(_json.dumps(profile.data, indent=2, default=str))
