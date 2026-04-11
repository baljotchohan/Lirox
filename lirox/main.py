"""Lirox v1.0.0 — Entry Point"""
import os
import sys
import time
import argparse


def fix_windows_path():
    """Auto-fix: add Python's Scripts dir to Windows PATH and re-exec so lirox starts."""
    if sys.platform != "win32":
        return

    import sysconfig
    scripts_dir = sysconfig.get_path("scripts")
    if not scripts_dir:
        return

    # winreg is Windows-only; import once here after the platform guard above
    try:
        import winreg as _winreg
    except ImportError:
        return  # should never happen on win32, but be safe

    path_env = os.environ.get("PATH", "")
    if scripts_dir.lower() in path_env.lower():
        return  # already present in the current session — nothing to do

    # BUG-H6 FIX: check the registry BEFORE deciding to re-exec.
    # If scripts_dir is already in the registry but not in the current shell
    # (e.g. freshly opened terminal), just update the env and return — no re-exec
    # needed, which would otherwise cause an infinite re-exec loop.
    try:
        with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, r"Environment", 0,
                             _winreg.KEY_READ) as key:
            try:
                reg_path, _ = _winreg.QueryValueEx(key, "PATH")
                if scripts_dir.lower() in reg_path.lower():
                    # Already persistent in registry — just update current env and return
                    os.environ["PATH"] = path_env.rstrip(";") + ";" + scripts_dir
                    return
            except FileNotFoundError:
                pass
    except Exception:
        pass

    # ── 1. Persist to the Windows registry (user-level) ──────────────────────
    try:
        key_path = r"Environment"
        with _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER, key_path, 0, _winreg.KEY_READ | _winreg.KEY_WRITE
        ) as key:
            try:
                current_reg, _ = _winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current_reg = ""
            # Only append if not already there
            if scripts_dir.lower() not in current_reg.lower():
                new_val = (current_reg.rstrip(";") + ";" + scripts_dir).lstrip(";")
                _winreg.SetValueEx(key, "PATH", 0, _winreg.REG_EXPAND_SZ, new_val)
        # Broadcast WM_SETTINGCHANGE so Explorer / new shells pick it up
        try:
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 2, 5000, None
            )
        except Exception:
            pass
        _patched = True
    except Exception:
        _patched = False

    # ── 2. Fix the current process env so lirox.exe is findable right now ────
    os.environ["PATH"] = path_env.rstrip(";") + ";" + scripts_dir

    if _patched:
        print(
            f"\n[Lirox] \u2705  PATH fixed: added Python Scripts to your user PATH.\n"
            f"         ({scripts_dir})\n"
            f"         New terminals will work automatically.\n",
            flush=True,
        )
    else:
        print(
            f"\n[Lirox] \u26a0\ufe0f  Could not write to registry. Please add manually:\n"
            f"         {scripts_dir}\n",
            flush=True,
        )

    # ── 3. Re-exec the current command so lirox itself starts cleanly ─────────
    # Use the lirox.exe that is now on PATH, or fall back to python -m lirox
    import shutil
    lirox_exe = shutil.which("lirox") or os.path.join(scripts_dir, "lirox.exe")
    if lirox_exe and os.path.isfile(lirox_exe):
        os.execv(lirox_exe, [lirox_exe] + sys.argv[1:])
    else:
        os.execv(sys.executable, [sys.executable, "-m", "lirox"] + sys.argv[1:])


def check_dependencies():
    required = {
        "rich": "rich", "prompt_toolkit": "prompt-toolkit",
        "psutil": "psutil", "dotenv": "python-dotenv",
        "bs4": "beautifulsoup4", "lxml": "lxml", "requests": "requests",
    }
    missing = [pkg for mod, pkg in required.items()
               if not _try_import(mod.split(".")[0])]
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


# BUG-1 FIX: guard module-level imports so check_dependencies() message
# actually shows when deps are missing.
try:
    from lirox.orchestrator.master import MasterOrchestrator
    from lirox.ui.display import (
        show_welcome, show_status_card, show_thinking, show_agent_event,
        show_answer, render_streaming_chunk, error_panel, info_panel,
        success_message, confirm_prompt, console,
    )
    from lirox.utils.llm import available_providers
    from lirox.config import APP_VERSION
except ImportError as _import_err:
    # Dependencies not installed yet — print friendly message
    check_dependencies()          # this will sys.exit with a helpful message
    # If check_dependencies didn't exit (shouldn't happen), re-raise
    raise


def get_prompt_label(agent_name: str) -> list:
    return [("class:prompt", f"[{agent_name}] "), ("class:symbol", "✦ ")]


def main():
    fix_windows_path()   # no-op on macOS/Linux; auto-fixes PATH on Windows
    check_dependencies()

    parser = argparse.ArgumentParser(description=f"Lirox v{APP_VERSION} — Personal AI Agent")
    parser.add_argument("--setup",   action="store_true", help="Run setup wizard")
    parser.add_argument("--update",  action="store_true", help="Update Lirox")
    parser.add_argument("--backup",  action="store_true", help="Backup agent data")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--verbose", action="store_true", help="Show thinking traces")
    args = parser.parse_args()

    if args.version:
        print(f"Lirox v{APP_VERSION}"); sys.exit(0)
    if args.update:
        run_update(); sys.exit(0)
    if args.backup:
        run_backup(); sys.exit(0)

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
    console.print("  [dim]Always-on deep thinking  ·  /help for commands[/]\n")

    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.completion import Completer, Completion

    agent_name = profile.data.get("agent_name", "Lirox")
    last_int   = 0.0
    style      = Style.from_dict({"prompt": "ansiyellow bold", "symbol": "ansiyellow"})

    commands = [
        "/help", "/setup", "/history", "/session", "/models", "/use-model", "/memory", "/think",
        "/profile", "/reset", "/test",
        "/train", "/learnings", "/add-skill", "/skills", "/use-skill",
        "/add-agent", "/agents",
        "/improve", "/apply", "/pending",
        "/soul", "/mind", "/restart",
        "/backup", "/import-memory", "/export-profile",
        "/uninstall", "/update", "/exit",
    ]

    class SlashCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor.lstrip()
            if not text.startswith("/"): return
            for cmd in commands:
                if cmd.startswith(text.lower()):
                    yield Completion(cmd, start_position=-len(text))

    session = PromptSession(completer=SlashCompleter(), complete_while_typing=True)

    while True:
        try:
            # BUG-H3 FIX: read agent name fresh each iteration so /setup changes take effect
            line = session.prompt(get_prompt_label(profile.data.get("agent_name", "Lirox")), style=style).strip()
            if not line: continue
            if line.lower() in ("exit", "quit", "/exit"):
                info_panel("Shutting down. Goodbye."); break
            if line.startswith("/"):
                handle_command(orchestrator, profile, line, verbose=args.verbose); continue
            if line.startswith("@"):
                handle_agent_query(line); continue
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


def process_query(orch: MasterOrchestrator, query: str, verbose: bool = False):
    last_agent   = "personal"
    status       = None
    was_streamed = False

    try:
        for ev in orch.run(query):
            t = ev.type

            if t == "thinking":
                if ev.message == "Analyzing…" and not verbose:
                    if status is None:
                        status = console.status("[bold purple]🧠 Thinking…[/]", spinner="dots")
                        status.start()
                elif verbose:
                    if status: status.stop(); status = None
                    show_thinking(ev.message)
                else:
                    if ev.message != "Analyzing…" and status:
                        status.stop(); status = None

            elif t == "plan_display":
                if status: status.stop(); status = None
                console.print(ev.message)

            elif t == "streaming":
                if status: status.stop(); status = None
                if not was_streamed:
                    agent_n = ev.agent or last_agent
                    icon    = "⚡" if agent_n == "personal" else "🧠"
                    color   = "bold #FFD700" if agent_n == "personal" else "bold #FFD54F"
                    console.print(f"\n{icon} [{color}]Response:[/]")
                    was_streamed = True
                render_streaming_chunk(ev.message)

            elif t == "done":
                if status: status.stop(); status = None
                if was_streamed:
                    console.print()
                    console.print("  [bold #10b981]✓ Done[/]")
                elif ev.message:
                    show_answer(ev.message, agent=last_agent)

            elif t == "auto_train":
                # BUG-C3 FIX: subtle indicator when auto-training extracts facts
                console.print(f"  [dim #10b981]{ev.message}[/]")

            else:
                if status and t in ("tool_call", "tool_result"):
                    status.stop(); status = None
                if t == "agent_start":
                    last_agent = ev.agent or last_agent
                    show_agent_event(ev.agent, t, ev.message)
                elif t in ("tool_call", "tool_result", "agent_progress"):
                    show_agent_event(ev.agent or last_agent, t, ev.message)
                elif t == "error":
                    show_agent_event(ev.agent or last_agent, "error", ev.message)
    finally:
        if status: status.stop()


def handle_agent_query(line: str) -> None:
    """Dispatch @agent_name query directly via SubAgentsRegistry."""
    from rich.panel import Panel as _Panel
    parts     = line.split(None, 1)
    agent_ref = parts[0].lstrip("@").lower()
    query     = parts[1].strip() if len(parts) > 1 else ""

    if not query:
        console.print(f"  [dim]Usage: @{agent_ref} <query>[/]")
        return

    from lirox.mind.agent import get_sub_agents
    registry = get_sub_agents()

    with console.status(f"[bold cyan]🤖 @{agent_ref} thinking…[/]", spinner="dots"):
        result = registry.run_agent(agent_ref, query)

    console.print(_Panel(result, title=f"[bold cyan]@{agent_ref}[/]",
                          border_style="cyan", padding=(1, 2)))


def _show_pending_diffs(imp) -> None:
    """BUG-C4 FIX: Display a unified diff for each pending patch so the user
    can review changes before approving /apply."""
    import difflib
    import json
    from pathlib import Path as _Path
    from rich.panel import Panel as _Panel
    from rich.syntax import Syntax
    from lirox.config import PROJECT_ROOT

    root = _Path(PROJECT_ROOT)
    patches_dir = imp._patches_dir

    for mf in sorted(patches_dir.glob("*.json")):
        try:
            meta = json.loads(mf.read_text())
            pf   = _Path(meta["patch_file"])
            orig = root / meta["original_file"]
            if not pf.exists() or not orig.exists():
                continue
            original_lines = orig.read_text(errors="replace").splitlines(keepends=True)
            patched_lines  = pf.read_text(errors="replace").splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(
                original_lines,
                patched_lines,
                fromfile=f"a/{meta['original_file']}",
                tofile=f"b/{meta['original_file']}",
                lineterm="",
            ))
            if diff_lines:
                diff_text = "\n".join(diff_lines)
                syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
                console.print(_Panel(
                    syntax,
                    title=f"[bold yellow]Diff — {meta['original_file']}[/]",
                    subtitle=f"[dim]{meta.get('issue', '')[:100]}[/]",
                    border_style="yellow",
                    padding=(0, 1),
                ))
        except Exception:
            pass  # If diff fails, user still sees the filename list above


def handle_command(orch: MasterOrchestrator, profile, cmd: str, verbose: bool = False):
    parts = cmd.strip().split()
    base  = parts[0].lower()

    if base == "/help":
        from rich.table import Table as _T
        from rich.panel import Panel as _P
        t = _T(show_header=True, header_style="bold #FFC107", border_style="dim")
        t.add_column("Command", style="bold white")
        t.add_column("Description", style="dim white")
        rows = [
            ("/help",               "Show this help"),
            ("/setup",              "Re-run setup wizard (API keys, profile, name…)"),
            ("/history [n]",        "Show last N sessions"),
            ("/session",            "Current session info"),
            ("/models",             "Available LLM providers"),
            ("/use-model <name>",   "Pin a provider for this session (groq, gemini, openai…)"),
            ("/memory",             "Memory stats"),
            ("/think <q>",          "Run thinking engine"),
            ("/profile",            "Show your profile"),
            ("/reset",              "Reset session memory"),
            ("/test",               "Run diagnostics"),
            ("/train",              "Extract permanent learnings from sessions"),
            ("/learnings",          "View all learned knowledge"),
            ("/add-skill <desc>",   "Generate a new skill via LLM"),
            ("/skills",             "List all skills"),
            ("/use-skill <n>",      "Execute a skill"),
            ("/add-agent <desc>",   "Generate a new sub-agent via LLM"),
            ("/agents",             "List all sub-agents"),
            ("@name <query>",       "Talk to a custom sub-agent"),
            ("/improve",            "Audit codebase and stage patches"),
            ("/pending",            "List patches waiting for review"),
            ("/apply",              "Apply all staged patches"),
            ("/soul",               "View agent soul"),
            ("/mind",               "Full Mind Agent state"),
            ("/backup",             "Backup all data to ~/.lirox_backup/"),
            ("/import-memory",      "Import from ChatGPT/Claude/Gemini export"),
            ("/export-profile",     "Export profile as JSON"),
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
            # BUG-H3 FIX: agent name is now read dynamically each prompt iteration,
            # so the updated name takes effect immediately without a restart.
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
        from lirox.utils.llm import available_providers as _avp, _PROVIDER_ENV_MAP
        target = parts[1].lower().strip() if len(parts) > 1 else ""
        valid  = list(_PROVIDER_ENV_MAP.keys()) + ["ollama", "hf_bnb", "auto"]
        if not target:
            avail  = _avp()
            pinned = os.getenv("_LIROX_PINNED_MODEL", "none")
            lines  = ["MODEL SWITCHER\n",
                      f"  Currently pinned : {pinned}",
                      f"  Available        : {', '.join(avail) or 'none'}",
                      "",
                      "  Usage: /use-model <provider>",
                      "  e.g.   /use-model groq",
                      "         /use-model gemini",
                      "         /use-model openai",
                      "         /use-model anthropic",
                      "         /use-model ollama",
                      "         /use-model auto    ← let Lirox choose"]
            info_panel("\n".join(lines))
        elif target not in valid:
            error_panel("UNKNOWN PROVIDER",
                        f"'{target}' is not recognised.\n"
                        f"Valid options: {', '.join(valid)}")
        else:
            os.environ["_LIROX_PINNED_MODEL"] = target
            # Patch the orchestrator's default provider so it takes effect immediately
            try:
                orch.default_provider = None if target == "auto" else target
            except AttributeError:
                pass  # orchestrator may not expose this attr; env var is still picked up
            if target == "auto":
                success_message("Model set to [auto] — Lirox will choose the best provider.")
            else:
                success_message(f"Model pinned to [{target}]. All queries will use this provider.\n"
                                f"  Switch back: /use-model auto")

    elif base == "/memory":
        lines = ["MEMORY STATS\n"]
        for at, mem in orch._agent_memory.items():
            s = mem.get_stats()
            lines.append(f"  {at.value:12}: {s['buffer_size']} msgs, "
                          f"{s.get('long_term_facts', 0)} facts")
        if not orch._agent_memory:
            lines.append("  Not yet activated.")
        gs = orch.global_memory.get_stats()
        lines.append(f"\n  Global memory: {gs['buffer_size']} msgs")
        info_panel("\n".join(lines))

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
            for mem in orch._agent_memory.values():
                mem.conversation_buffer.clear()
            orch.global_memory.conversation_buffer.clear()
            orch.session_store.new_session()
            success_message("Memory reset. New session started.")

    elif base == "/test":
        info_panel("Running diagnostics…")
        tests = [
            ("Providers",     lambda: ", ".join(available_providers()) or "None"),
            ("Global Memory", lambda: f"{orch.global_memory.get_stats()['buffer_size']} buffered"),
            ("Sessions",      lambda: f"{len(orch.session_store.list_sessions())} sessions"),
            ("Thinking",      lambda: "Always-on"),
            ("Version",       lambda: f"v{APP_VERSION}"),
            ("Architecture",  lambda: "MindAgent + PersonalAgent"),
        ]
        for name, fn in tests:
            try: console.print(f"  [green]✓[/] {name:22}: {fn()}")
            except Exception as e: console.print(f"  [red]✖[/] {name:22}: {e}")
        success_message("Diagnostics complete.")

    elif base == "/train":
        info_panel("Analyzing sessions and extracting learnings…")
        from lirox.mind.agent import get_trainer
        stats = get_trainer(orch.global_memory).train(orch.global_memory, orch.session_store)
        success_message(
            f"Training complete!\n"
            f"  Facts learned     : {stats.get('facts_added', 0)}\n"
            f"  Topics updated    : {stats.get('topics_bumped', 0)}\n"
            f"  Preferences found : {stats.get('preferences_added', 0)}\n"
            f"  Projects found    : {stats.get('projects_found', 0)}")

    elif base == "/learnings":
        from lirox.mind.agent import get_learnings
        learn = get_learnings()
        info_panel(f"🧠 LEARNINGS\n\n"
                   f"{learn.to_context_string() or 'Nothing learned yet — chat and /train'}\n\n"
                   f"STATS: {learn.stats_summary()}")

    elif base == "/soul":
        from lirox.mind.agent import get_soul
        info_panel(f"👻 LIVING SOUL\n\n{get_soul().display_summary()}")

    elif base == "/mind":
        from lirox.mind.agent import get_soul, get_learnings, get_skills, get_sub_agents
        soul = get_soul()
        ls   = get_learnings().stats_summary()
        sk   = len(get_skills().list_skills())
        sa   = len(get_sub_agents().list_agents())
        info_panel(
            f"🧠 MIND AGENT STATE\n\n"
            f"  Identity : {soul.get_name()}\n"
            f"  Nature   : {soul.state['personality'].get('core', '')[:60]}\n\n"
            f"  Knowledge: {ls}\n"
            f"  Skills   : {sk} loaded\n"
            f"  Agents   : {sa} loaded\n"
            f"  Age      : {soul.state.get('interaction_count', 0)} interactions")

    elif base == "/improve":
        info_panel("Auditing codebase… (may take a minute)")
        from lirox.mind.agent import get_improver
        imp = get_improver()
        res = imp.improve()
        details = "\n".join(
            f"  • {i.get('file', '?')}: "
            f"{i.get('issue', i.get('error', i.get('status', '')))[:80]}"
            for i in res.get("improvements", [])
        ) or "  Nothing found."
        success_message(
            f"Audit complete.\n"
            f"  Files audited  : {res['files_audited']}\n"
            f"  Issues found   : {res['issues_found']}\n"
            f"  Patches staged : {res.get('patches_staged', 0)}\n\n"
            f"Review with /pending, commit with /apply:\n{details}")
        from rich.markdown import Markdown
        console.print(Markdown("### Suggestions\n" + imp.suggest_improvements()))

    elif base == "/pending":
        from lirox.mind.agent import get_improver
        patches = get_improver().list_pending_patches()
        if not patches:
            info_panel("No pending patches. Run /improve to generate some.")
        else:
            lines = [f"PENDING PATCHES ({len(patches)})\n"]
            for p in patches:
                lines.append(f"  • {p['file']}: {p['issue'][:80]}")
            lines.append("\nRun /apply to commit all patches.")
            info_panel("\n".join(lines))

    elif base == "/apply":
        from lirox.mind.agent import get_improver
        imp     = get_improver()
        patches = imp.list_pending_patches()
        if not patches:
            info_panel("No pending patches."); return
        console.print(f"\n  [bold #FFC107]{len(patches)} patch(es) ready:[/]")
        for p in patches:
            console.print(f"  • {p['file']}: {p['issue'][:80]}")

        # BUG-C4 FIX: Show unified diff of what will change before asking to apply
        _show_pending_diffs(imp)

        if confirm_prompt("Apply all patches? (backups created automatically)"):
            res = imp.apply_pending_patches()
            success_message(f"Applied: {res['applied']}  Failed: {res['failed']}")
            for d in res.get("details", []):
                console.print(f"  • {d.get('file', '?')}: "
                               f"{d.get('status', d.get('error', '?'))}")
            # BUG-C2 FIX: Restart Lirox after successful patch application so
            # the patched code is loaded immediately (mirrors /restart behavior).
            if res["applied"] > 0:
                info_panel("🔄 Restarting Lirox with patched code…")
                time.sleep(1)
                os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            info_panel("Cancelled. Patches remain in data/pending_patches/")

    elif base == "/add-skill":
        desc = cmd[10:].strip()
        if not desc:
            info_panel("Usage: /add-skill <description of what the skill should do>")
        else:
            info_panel(f"Building skill: {desc[:60]}…")
            from lirox.mind.agent import get_skills
            try:
                res  = get_skills().build_skill_from_description(desc)
                if res.get("success"):
                    name = res.get("name", "?")
                    path = res.get("path", "")
                    success_message(f"✅ Skill '{name}' created!\n"
                                    f"   Saved: {path}\n"
                                    f"   Use:   /use-skill {name}")
                else:
                    error_panel("SKILL FAILED", res.get("error", "Unknown error"))
            except Exception as e:
                error_panel("SKILL ERROR", str(e))

    elif base == "/skills":
        from lirox.mind.agent import get_skills
        skills = get_skills().list_skills()
        if not skills:
            info_panel("No skills found. Use /add-skill to create one.")
        else:
            lines = [f"AVAILABLE SKILLS ({len(skills)})\n"]
            for s in skills:
                lines.append(f"  • {s['name']}: {s.get('description', '-')[:80]}")
                lines.append(f"    Use: /use-skill {s['name']}")
            info_panel("\n".join(lines))

    elif base == "/use-skill":
        rest = cmd[len("/use-skill"):].strip()
        if not rest:
            info_panel("Usage: /use-skill <name> [key=value ...]\n\n"
                       "Example: /use-skill summarize_text input='hello world'")
        else:
            sp         = rest.split(None, 1)
            skill_name = sp[0]
            raw_params = sp[1] if len(sp) > 1 else ""
            params: dict = {}
            if raw_params:
                import shlex
                for token in shlex.split(raw_params):
                    if "=" in token:
                        k, v = token.split("=", 1)
                        params[k.strip()] = v.strip()
                    else:
                        params["input"] = token

            # BUG-2 FIX: extract real query value instead of passing str(params)
            # Priority: "input" key → "text" key → "query" key → first value → empty
            query_for_skill = (
                params.get("input") or
                params.get("text") or
                params.get("query") or
                (next(iter(params.values()), "") if params else "") or
                skill_name  # fallback: use skill name as minimal context
            )

            result = None
            # Try SkillsRegistry (.py skills from /add-skill) first
            try:
                from lirox.mind.agent import get_skills
                reg = get_skills()
                if skill_name.lower() in [s["name"].lower() for s in reg.list_skills()]:
                    with console.status(f"[bold cyan]⚙️ Running '{skill_name}'…[/]",
                                        spinner="dots"):
                        result = reg.run_skill(skill_name, query_for_skill, params)
            except Exception:
                pass

            # Fallback to SkillExecutor (.json skills)
            if result is None:
                from lirox.skills.executor import SkillExecutor
                with console.status(f"[bold cyan]⚙️ Running '{skill_name}'…[/]",
                                    spinner="dots"):
                    result = SkillExecutor().run(skill_name, params)

            show_answer(result or "Skill returned no output.", agent="skill")

    elif base == "/add-agent":
        desc = cmd[10:].strip()
        if not desc:
            info_panel("Usage: /add-agent <description — include the name you want>")
        else:
            import re
            nm = (re.search(r'(?:name[d]?|called|as)\s+["\']?([A-Za-z][A-Za-z0-9_]+)["\']?',
                            desc, re.IGNORECASE)
                  or re.search(r'@([A-Za-z][A-Za-z0-9_]+)', desc)
                  or re.search(r'\b([A-Z][a-z][a-zA-Z0-9_]+)\b', desc))
            agent_name = nm.group(1) if nm else "CustomAgent"
            info_panel(f"Building agent '{agent_name}'…")
            from lirox.mind.agent import get_sub_agents
            try:
                res = get_sub_agents().build_agent_from_description(desc, name=agent_name)
                if res.get("success"):
                    name = res.get("name", agent_name)
                    path = res.get("path", "")
                    success_message(f"✅ Agent '{name}' created!\n"
                                    f"   Saved: {path}\n"
                                    f"   Use:   @{name} <query>")
                else:
                    error_panel("AGENT FAILED", res.get("error", "Unknown error"))
            except Exception as e:
                error_panel("AGENT ERROR", str(e))

    elif base == "/agents":
        from lirox.mind.agent import get_sub_agents
        agents = get_sub_agents().list_agents()
        if not agents:
            info_panel("No agents found. Use /add-agent to create one.")
        else:
            lines = [f"AVAILABLE AGENTS ({len(agents)})\n"]
            for a in agents:
                lines.append(f"  • @{a['name']}: {a.get('description', '-')[:80]}")
                lines.append(f"    Use: @{a['name']} <query>")
            info_panel("\n".join(lines))

    elif base == "/restart":
        info_panel("🔄 Restarting…")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    elif base == "/backup":
        run_backup()

    elif base in ("/uninstall", "/update", "/import-memory", "/export-profile"):
        _legacy_commands(orch, profile, cmd, base)

    else:
        console.print(f"  [dim]Unknown command: {base}. Type /help.[/]")


def run_update():
    import subprocess
    from lirox.config import PROJECT_ROOT
    info_panel("Checking for updates…")
    try:
        if os.path.exists(os.path.join(PROJECT_ROOT, ".git")):
            result = subprocess.run(["git", "-C", PROJECT_ROOT, "pull"],
                                    capture_output=True, text=True, check=True)
            if "Already up to date." in result.stdout:
                success_message("Already up to date.")
            else:
                console.print(f"[dim]{result.stdout.strip()}[/]")
                subprocess.run([sys.executable, "-m", "pip", "install", "-e", PROJECT_ROOT],
                               capture_output=True)
                success_message("Updated. Please restart.")
        else:
            info_panel("Not a git repo.\nRun: pip install --upgrade lirox")
    except Exception as e:
        error_panel("UPDATE FAILED", str(e))


def run_backup():
    import shutil
    from lirox.config import DATA_DIR, PROJECT_ROOT
    from pathlib import Path
    from datetime import datetime
    backup_dir = Path.home() / ".lirox_backup"
    backup_dir.mkdir(exist_ok=True)
    dest = backup_dir / f"lirox_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copytree(DATA_DIR, str(dest))
        pf = Path(PROJECT_ROOT) / "profile.json"
        if pf.exists():
            shutil.copy2(pf, dest / "profile.json")
        success_message(f"Backup saved to: {dest}")
    except Exception as e:
        error_panel("BACKUP FAILED", str(e))


def _legacy_commands(orch, profile, cmd, base):
    import shutil
    from lirox.config import PROJECT_ROOT, DATA_DIR, OUTPUTS_DIR
    from rich.panel import Panel as _P

    if base == "/uninstall":
        console.print(_P(
            "[bold red]⚠️  UNINSTALL[/]\n\nDeletes ALL data. "
            "Package removal: pip uninstall lirox",
            border_style="red"))
        if confirm_prompt("Delete ALL Lirox data?"):
            for path in [os.path.join(PROJECT_ROOT, "profile.json"),
                          os.path.join(PROJECT_ROOT, ".env")]:
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
        console.print("\n  [bold #FFC107]Import memory from export file:[/]")
        filepath = console.input("  [dim]Path to file: [/]").strip()
        if filepath:
            from lirox.memory.import_handler import MemoryImporter
            from lirox.mind.agent import get_learnings
            info_panel("Importing…")
            res = MemoryImporter(get_learnings()).import_file(filepath)
            if "error" in res:
                error_panel("IMPORT ERROR", res["error"])
            else:
                success_message(
                    f"Imported: {res['imported']} messages · "
                    f"{res['facts_added']} facts")

    elif base == "/export-profile":
        import json as _json
        console.print(_json.dumps(profile.data, indent=2, default=str))
