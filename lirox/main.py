"""Lirox v1.1 — Entry Point"""
import os
import sys
import time
import argparse
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


def main():
    # ── Bootstrap FIRST — before any heavy imports ──
    check_dependencies()

    # ── Ensure data directories exist ──
    from lirox.config import ensure_directories
    ensure_directories()

    # ── Now safe to import everything ──
    from lirox.orchestrator.master import MasterOrchestrator
    from lirox.ui.display import (
        show_welcome, show_status_card, show_answer,
        render_streaming_chunk, error_panel, info_panel,
        success_message, confirm_prompt, console, show_thinking,
        show_agent_event, show_thinking_phase,
        show_thinking_panel_open, show_thinking_panel_close,
    )
    from lirox.utils.llm import available_providers
    from lirox.config import APP_VERSION

    parser = argparse.ArgumentParser(description=f"Lirox v{APP_VERSION}")
    parser.add_argument("--setup",   action="store_true", help="Run setup wizard")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--verbose", action="store_true", help="Show thinking traces")
    args = parser.parse_args()

    if args.version:
        print(f"Lirox v{APP_VERSION}"); sys.exit(0)

    from lirox.agent.profile import UserProfile
    profile      = UserProfile()
    orchestrator = MasterOrchestrator(profile_data=profile.data)

    show_welcome()

    if not profile.is_setup() or args.setup:
        from lirox.ui.wizard import run_setup_wizard
        try:
            run_setup_wizard(profile)
            orchestrator.profile_data = profile.data
        except KeyboardInterrupt:
            console.print("\n  [dim]Setup skipped.[/]")

    show_status_card(profile.data, available_providers())
    console.print(f"  [dim]Workspace: {os.getenv('LIROX_WORKSPACE', str(Path.home() / 'Desktop'))}[/]")
    console.print("  [dim]Type /help for commands  ·  /setup to configure[/]\n")

    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.completion import Completer, Completion

    last_int = 0.0
    style    = Style.from_dict({"prompt": "ansiyellow bold", "symbol": "ansiyellow"})

    cmd_docs = {
        "/help": "Show this help",
        "/setup": "Re-run setup wizard",
        "/history": "Show last N sessions",
        "/session": "Current session info",
        "/models": "Available LLM providers",
        "/use-model": "Pin a provider (groq, gemini, openai…)",
        "/memory": "Memory stats",
        "/profile": "Show your profile",
        "/reset": "Reset session memory",
        "/test": "Run diagnostics",
        "/train": "Extract learnings from conversations",
        "/recall": "Show everything Lirox knows about you",
        "/workspace": "Show or change workspace directory",
        "/backup": "Backup all data",
        "/export-memory": "Export profile + learnings as JSON",
        "/import-memory": "Import from ChatGPT/Claude/Gemini/Lirox export",
        "/restart": "Restart Lirox",
        "/update": "Update to latest version",
        "/uninstall": "Remove all Lirox data",
        "/exit": "Shutdown",
    }

    class SlashCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor.lstrip()
            if not text.startswith("/"): return
            for cmd, desc in cmd_docs.items():
                if cmd.startswith(text.lower()):
                    yield Completion(cmd, start_position=-len(text), display_meta=desc)

    session = PromptSession(completer=SlashCompleter(), complete_while_typing=True)

    while True:
        try:
            line = session.prompt(
                get_prompt_label(profile.data.get("agent_name", "Lirox")),
                style=style
            ).strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit", "/exit"):
                info_panel("Shutting down. Goodbye."); break
            if line.startswith("/"):
                handle_command(orchestrator, profile, line, verbose=args.verbose)
                continue
            process_query(orchestrator, line, verbose=args.verbose)
        except KeyboardInterrupt:
            now = time.time()
            if now - last_int < 2.0:
                print("\n[!] Force quit."); sys.exit(0)
            print("\n[!] Ctrl+C again to quit, or type /exit.")
            last_int = now
        except EOFError:
            info_panel("Shutting down. Goodbye."); break
        except Exception as e:
            error_panel("KERNEL ERROR", str(e))


def process_query(orch, query: str, verbose: bool = False):
    from lirox.ui.display import console
    from lirox.mind.cognitive_engine import CognitiveEngine, CognitiveContext, ThinkingDisplay
    from lirox.mind.bridge import cognitive_llm_call, cognitive_tool_executor
    import os

    # Register user query in memory
    session = orch.session_store.current()
    session.add("user", query, agent="personal")

    # Build conversation history
    history = []
    for entry in session.entries[-6:]:
        if entry.role in ("user", "assistant"):
            history.append({"role": entry.role, "content": entry.content})

    context = CognitiveContext(
        user_name=orch.profile_data.get("name", ""),
        workspace=os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop")),
        available_tools=["list_files", "read_file", "write_file", "edit_file", "create_presentation", "create_pdf"],
        conversation_history=history
    )
    
    display = ThinkingDisplay(console)
    engine = CognitiveEngine(
        context=context,
        llm_call=cognitive_llm_call,
        tool_executor=cognitive_tool_executor,
        display=display
    )
    
    result = engine.process(query)
    
    console.print("\n⚡ Response:")
    console.print(result["response"])
    console.print("✓ Done")
    
    # Store assistant response and auto train
    orch.global_memory.save_exchange(query, result["response"])
    session.add("assistant", result["response"], agent="personal")
    orch.session_store.save_current()
    orch._interaction_count += 1
    if orch._interaction_count % 20 == 0:
        orch._auto_train()


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
            ("/train",              "Extract learnings from conversations"),
            ("/recall",             "Show everything Lirox knows about you"),
            ("/workspace [path]",   "Show or change workspace directory"),
            ("/backup",             "Backup all data"),
            ("/export-memory",      "Export profile + learnings as JSON"),
            ("/import-memory",      "Import from ChatGPT/Claude/Gemini/Lirox export"),
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
        info_panel(f"CURRENT SESSION\n\n"
                   f"  Name    : {s.name or f'Session {s.session_id}'}\n"
                   f"  ID      : {s.session_id}\n"
                   f"  Messages: {len(s.entries)}\n"
                   f"  Started : {s.created_at[:16].replace('T', ' ')}")

    elif base == "/models":
        p = available_providers()
        pinned = os.getenv("_LIROX_PINNED_MODEL", "")
        pin_note = f"\n\n  📌 Pinned: {pinned}" if pinned else ""
        info_panel("AVAILABLE LLM PROVIDERS\n\n" +
                   ("\n".join(f"  ✓ {x}" for x in p) if p else
                    "  None configured — run /setup") + pin_note)

    elif base == "/use-model":
        from lirox.utils.llm import _PROVIDER_ENV_MAP
        target = parts[1].lower().strip() if len(parts) > 1 else ""
        valid  = list(_PROVIDER_ENV_MAP.keys()) + ["ollama", "auto"]
        if not target:
            avail  = available_providers()
            pinned = os.getenv("_LIROX_PINNED_MODEL", "none")
            info_panel(f"Currently pinned: {pinned}\n"
                       f"Available: {', '.join(avail) or 'none'}\n\n"
                       f"Usage: /use-model <provider>\n"
                       f"  /use-model auto    ← let Lirox choose")
        elif target not in valid:
            error_panel("UNKNOWN PROVIDER", f"'{target}' not recognised.\nValid: {', '.join(valid)}")
        else:
            os.environ["_LIROX_PINNED_MODEL"] = target
            if target == "auto":
                success_message("Model set to [auto].")
            else:
                success_message(f"Model pinned to [{target}]. Switch back: /use-model auto")

    elif base == "/memory":
        gs = orch.global_memory.get_stats()
        info_panel(f"MEMORY STATS\n\n"
                   f"  Buffer messages : {gs['buffer_size']}\n"
                   f"  Long-term facts : {gs.get('long_term_facts', 0)}")

    elif base == "/profile":
        info_panel(f"PROFILE\n\n{profile.summary()}")

    elif base == "/reset":
        if confirm_prompt("Reset all session memory?"):
            orch.global_memory.conversation_buffer.clear()
            orch.session_store.new_session()
            success_message("Memory reset. New session started.")

    elif base == "/test":
        info_panel("Running diagnostics…")
        tests = [
            ("Providers",     lambda: ", ".join(available_providers()) or "None"),
            ("Global Memory", lambda: f"{orch.global_memory.get_stats()['buffer_size']} buffered"),
            ("Sessions",      lambda: f"{len(orch.session_store.list_sessions())} sessions"),
            ("Workspace",     lambda: os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop"))),
            ("Version",       lambda: f"v{APP_VERSION}"),
        ]
        for name, fn in tests:
            try:
                console.print(f"  [green]✓[/] {name:22}: {fn()}")
            except Exception as e:
                console.print(f"  [red]✖[/] {name:22}: {e}")
        success_message("Diagnostics complete.")

    elif base == "/train":
        from lirox.mind.trainer import TrainingEngine
        from lirox.mind.learnings import LearningsStore
        console.print("  [dim #a78bfa]🧠 Extracting learnings from conversations…[/]")
        try:
            learnings = LearningsStore()
            trainer = TrainingEngine(learnings)
            with console.status("[bold #a78bfa]Training…[/]", spinner="dots"):
                stats = trainer.train(orch.global_memory, orch.session_store)
        except KeyboardInterrupt:
            console.print("\n  [dim]Training interrupted.[/]")
            return
        except Exception as e:
            error_panel("TRAINING ERROR", str(e))
            return

        total = stats.get("facts_added", 0) + stats.get("topics_bumped", 0) + stats.get("preferences_added", 0)
        if total == 0:
            info_panel("🧠 Training complete — nothing new to learn yet.\n"
                       "Chat more first, then run /train again.")
        else:
            success_message(
                f"Training complete!\n"
                f"  ✓ Facts       : {stats.get('facts_added', 0)} new\n"
                f"  ✓ Topics      : {stats.get('topics_bumped', 0)} updated\n"
                f"  ✓ Preferences : {stats.get('preferences_added', 0)} captured\n"
                f"  ✓ Projects    : {stats.get('projects_found', 0)} found\n\n"
                f"  Run /recall to see everything I know.")

    elif base == "/recall":
        from lirox.mind.learnings import LearningsStore
        from lirox.mind.soul import LivingSoul
        learn = LearningsStore()
        soul  = LivingSoul()
        agent_name = profile.data.get("agent_name", soul.get_name())
        user_name  = profile.data.get("user_name", "")

        lines = [f"🧠 WHAT {agent_name.upper()} KNOWS ABOUT {user_name.upper() if user_name else 'YOU'}\n"]
        facts = learn.get_facts_summary(n=15)
        if facts and "No facts" not in facts:
            lines.append(f"FACTS:\n{facts}\n")
        projects = learn.data.get("projects", [])
        if projects:
            lines.append("PROJECTS:")
            for p in projects[-5:]:
                lines.append(f"  • {p['name']}: {p.get('description', '–')}")
            lines.append("")
        topics = learn.get_top_topics(8)
        if topics:
            lines.append("INTERESTS: " + ", ".join(t["topic"] for t in topics))
        lines.append(f"\n{learn.stats_summary()}")
        lines.append("\nRun /train to extract more from recent conversations.")
        info_panel("\n".join(lines))

    elif base == "/workspace":
        new_path = cmd[len("/workspace"):].strip()
        if not new_path:
            current_ws = os.getenv("LIROX_WORKSPACE", str(Path.home() / "Desktop"))
            info_panel(f"WORKSPACE\n\n  Current: {current_ws}\n\n"
                       f"  Usage: /workspace ~/Projects/myapp")
        else:
            expanded = os.path.expanduser(new_path)
            if os.path.isdir(expanded):
                os.environ["LIROX_WORKSPACE"] = expanded
                # FIX-08: Also update the live config module attribute
                import lirox.config as _cfg
                _cfg.WORKSPACE_DIR = expanded
                _cfg.SAFE_DIRS_RESOLVED = [os.path.realpath(d) for d in _cfg.SAFE_DIRS]
                success_message(f"Workspace set to: {expanded}")
            else:
                error_panel("INVALID PATH", f"'{expanded}' does not exist or is not a directory.")

    elif base == "/backup":
        _run_backup()

    elif base == "/export-memory":
        _export_memory()

    elif base == "/import-memory":
        path = cmd[len("/import-memory"):].strip()
        if not path:
            path = console.input("  [dim]Path to file: [/]").strip()
        if path:
            _import_memory(path.strip("'\""))

    elif base == "/restart":
        info_panel("🔄 Restarting…")
        time.sleep(1)
        import subprocess
        args_list = [sys.executable] + sys.argv
        if sys.platform == "win32":
            subprocess.Popen(args_list, creationflags=subprocess.CREATE_NEW_CONSOLE)
            sys.exit(0)
        else:
            os.execv(sys.executable, args_list)

    elif base == "/update":
        _run_update()

    elif base == "/uninstall":
        import shutil
        from lirox.config import DATA_DIR, OUTPUTS_DIR
        from rich.panel import Panel as _P
        console.print(_P(
            "[bold red]⚠️  UNINSTALL[/]\n\nDeletes ALL data.",
            border_style="red"))
        if confirm_prompt("Delete ALL Lirox data?"):
            for path in [os.path.join(os.path.dirname(os.path.dirname(__file__)), "profile.json"),
                          os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")]:
                if os.path.exists(path): os.remove(path)
            for dp in [DATA_DIR, OUTPUTS_DIR]:
                if os.path.exists(dp): shutil.rmtree(dp, ignore_errors=True)
            success_message("All data deleted.")
            sys.exit(0)

    else:
        console.print(f"  [dim]Unknown command: {base}. Type /help.[/]")


# ── Utility functions ──

def _check_git_available() -> bool:
    import shutil
    return shutil.which("git") is not None


def _stash_changes(root: str) -> bool:
    from lirox.ui.display import console
    import subprocess
    try:
        status = subprocess.run(
            ["git", "-C", root, "status", "--porcelain"],
            capture_output=True, text=True, timeout=15,
        )
        if not status.stdout.strip():
            return True
        stash = subprocess.run(
            ["git", "-C", root, "stash", "--include-untracked"],
            capture_output=True, text=True, timeout=30,
        )
        if stash.returncode == 0:
            console.print("[dim]Local changes stashed before update.[/]")
            return True
        console.print(
            f"[yellow]Warning: could not stash changes "
            f"({stash.stderr.strip() or stash.stdout.strip()})[/]"
        )
        return False
    except Exception as exc:
        console.print(f"[yellow]Warning: stash check failed: {exc}[/]")
        return False


def _git_pull_with_retry(root: str, max_attempts: int = 3):
    from lirox.ui.display import console
    import subprocess
    import time as _time
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                ["git", "-C", root, "pull"],
                capture_output=True, text=True, timeout=120, check=True,
            )
            return True, result.stdout.strip(), ""
        except subprocess.CalledProcessError as exc:
            last_error = exc.stderr.strip() if exc.stderr else exc.stdout.strip()
            if attempt < max_attempts:
                wait = 2 ** (attempt - 1)
                console.print(f"[yellow]Pull attempt {attempt}/{max_attempts} failed (retrying in {wait}s)…[/]")
                _time.sleep(wait)
        except subprocess.TimeoutExpired:
            last_error = "git pull timed out after 120 s"
            if attempt < max_attempts:
                wait = 2 ** (attempt - 1)
                console.print(f"[yellow]Pull attempt {attempt}/{max_attempts} timed out (retrying in {wait}s)…[/]")
                _time.sleep(wait)
        except OSError as exc:
            last_error = str(exc)
            break
    return False, "", last_error


def _run_update():
    from lirox.ui.display import console, error_panel, info_panel, success_message
    from lirox.config import PROJECT_ROOT
    import subprocess
    import logging
    root = str(Path(PROJECT_ROOT).resolve())
    info_panel(f"Checking for updates in {root}…")
    if not _check_git_available():
        error_panel("UPDATE FAILED", "git is not installed or not on PATH.\nInstall git or run:  pip install --upgrade lirox")
        return
    git_dir = os.path.join(root, ".git")
    if not os.path.exists(git_dir):
        info_panel(f"Not a git repository ({root}).\nRun: pip install --upgrade lirox")
        return
    try:
        stash_ok = _stash_changes(root)
        if not stash_ok:
            error_panel("UPDATE FAILED", "Could not stash local changes.")
            return
        console.print("[dim]Pulling latest changes…[/]")
        pulled, stdout, pull_err = _git_pull_with_retry(root)
        if not pulled:
            error_panel("UPDATE FAILED", f"git pull failed:\n{pull_err}")
            return
        if "Already up to date." in stdout:
            success_message("Already up to date.")
            return
        if stdout:
            console.print(f"[dim]{stdout}[/]")
        console.print("[dim]Reinstalling package…[/]")
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", root],
            capture_output=True, text=True,
        )
        if pip_result.returncode != 0:
            pip_err = pip_result.stderr.strip() or pip_result.stdout.strip()
            error_panel("UPDATE PARTIALLY FAILED", f"git pull succeeded but pip install failed:\n{pip_err}")
            return
        success_message("Updated successfully. Please restart Lirox.")
    except Exception as exc:
        error_panel("UPDATE FAILED", str(exc))


def _run_backup():
    from lirox.ui.display import success_message, error_panel
    import shutil
    from lirox.config import DATA_DIR, PROJECT_ROOT
    from datetime import datetime
    backup_dir = Path.home() / ".lirox_backup"
    backup_dir.mkdir(exist_ok=True)
    dest = backup_dir / f"lirox_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        data_path = Path(DATA_DIR)
        if data_path.exists():
            shutil.copytree(str(data_path), str(dest), dirs_exist_ok=True)
        pf = Path(PROJECT_ROOT) / "profile.json"
        if pf.exists():
            shutil.copy2(str(pf), str(dest / "profile.json"))
        success_message(f"Backup saved to: {dest}")
    except Exception as e:
        error_panel("BACKUP FAILED", str(e))


def _export_memory():
    from lirox.ui.display import success_message
    import json
    from datetime import datetime
    from lirox.config import PROJECT_ROOT, MIND_LEARN_FILE
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = str(Path.home() / f"lirox_memory_export_{timestamp}.json")
    data = {"format_version": "1.0", "exported_at": datetime.now().isoformat(),
            "profile": {}, "learnings": {}}
    pf = os.path.join(PROJECT_ROOT, "profile.json")
    if os.path.exists(pf):
        try:
            with open(pf) as f: data["profile"] = json.load(f)
        except Exception: pass
    if os.path.exists(MIND_LEARN_FILE):
        try:
            with open(MIND_LEARN_FILE) as f: data["learnings"] = json.load(f)
        except Exception: pass
    with open(output_path, "w") as f:
        json.dump(data, f, indent=4)
    success_message(f"Exported to: {output_path}")


def _import_memory(file_path: str):
    from lirox.ui.display import error_panel, success_message
    import json
    path = Path(file_path)
    if not path.exists():
        error_panel("IMPORT ERROR", f"File not found: {file_path}")
        return
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw)
    except Exception as e:
        error_panel("IMPORT ERROR", f"Cannot parse file: {e}")
        return
    from lirox.mind.learnings import LearningsStore
    store = LearningsStore()
    facts_added = 0
    if "learnings" in data and isinstance(data["learnings"], dict):
        for f in data["learnings"].get("user_facts", []):
            fact_text = f.get("fact") if isinstance(f, dict) else str(f)
            store.add_fact(fact_text, confidence=0.85, source="import")
            facts_added += 1
    elif isinstance(data, list):
        for conv in data[:50]:
            mapping = conv.get("mapping", {})
            for node in mapping.values():
                msg = (node or {}).get("message")
                if msg and msg.get("author", {}).get("role") == "user":
                    content = ""
                    for p in msg.get("content", {}).get("parts", []):
                        if isinstance(p, str): content += p
                    if len(content) > 10:
                        store.add_fact(content[:200], confidence=0.7, source="chatgpt_import")
                        facts_added += 1
    success_message(f"Imported {facts_added} facts from {path.name}")
