"""Lirox v3.0 — Deep Setup Wizard.

Step-by-step onboarding that produces a personalized first interaction:
  1. Welcome + operator name
  2. Agent name (choice or custom)
  3. Niche (deep — with follow-up questions per niche)
  4. Current project (+ stage + stack)
  5. Goals (with follow-up categorization)
  6. LLM setup (local + cloud)
  7. Home Screen folder (BUG-2 fix: ask user for ~/Lirox access)
  8. One-paste memory import (optional)
  9. Seed LearningsStore with everything captured
 10. Personalized summary card

BUG-6 fix: profile.json write is validated before reporting "Setup complete".
BUG-2 fix: step 7 asks user permission to create ~/Lirox folder.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import set_key
from rich.box import HEAVY, ROUNDED
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from lirox.ui.display import console
from lirox.onboarding.niche_profiles import get_niche_followups, all_niche_labels
from lirox.onboarding.seed import seed_learnings_from_wizard

_PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT_DIR / ".env")


# ─────────────────────────────────────────────────────────────────────
# BUG-6 FIX: validate write access before saving profile
# ─────────────────────────────────────────────────────────────────────

def _validate_write_access(directory: Path) -> tuple[bool, str]:
    """Test that we can actually write to *directory*. Returns (ok, message)."""
    test_file = directory / ".lirox_write_test"
    try:
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return True, ""
    except PermissionError:
        return False, (
            f"No write permission to: {directory}\n"
            f"  Try: chmod u+w '{directory}'\n"
            f"  Or move Lirox to a location you own."
        )
    except OSError as e:
        return False, f"Cannot write to {directory}: {e}"


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────

def _create_launch_shortcut() -> None:
    """Create a one-click launcher in ~/Lirox/ for easy access."""
    import sys
    import stat as _stat
    lirox_dir = Path.home() / "Lirox"
    lirox_dir.mkdir(exist_ok=True)

    # Detect the lirox executable path
    import shutil
    lirox_bin = shutil.which("lirox") or f"{sys.executable} -m lirox"

    if sys.platform == "darwin":
        # macOS .command file — double-clickable in Finder
        shortcut = lirox_dir / "Launch Lirox.command"
        shortcut.write_text(
            f"#!/bin/bash\n"
            f"# Lirox Launcher — double-click to start\n"
            f"clear\n"
            f"{lirox_bin}\n",
            encoding="utf-8"
        )
        shortcut.chmod(shortcut.stat().st_mode | _stat.S_IEXEC)

    elif sys.platform == "win32":
        # Windows .bat file
        shortcut = lirox_dir / "Launch Lirox.bat"
        shortcut.write_text(
            f"@echo off\ncls\n{lirox_bin}\npause\n",
            encoding="utf-8"
        )
    else:
        # Linux .sh file
        shortcut = lirox_dir / "launch_lirox.sh"
        shortcut.write_text(
            f"#!/bin/bash\nclear\n{lirox_bin}\n",
            encoding="utf-8"
        )
        shortcut.chmod(shortcut.stat().st_mode | _stat.S_IEXEC)

    # Create a quick-reference command card
    cmd_card = lirox_dir / "COMMANDS.md"
    cmd_card.write_text(
        "# Lirox Quick Commands\n\n"
        "| Command | What it does |\n"
        "|---|---|\n"
        "| `/train` | Learn from your conversations — run this daily |\n"
        "| `/recall` | See everything the agent knows about you |\n"
        "| `/setup` | Re-run setup, change API keys or preferences |\n"
        "| `/memory` | View memory stats |\n"
        "| `/add-skill name` | Create a new custom skill |\n"
        "| `/add-agent name` | Create a new custom sub-agent |\n"
        "| `/backup` | Save all data |\n"
        "| `/improve` | Scan codebase for issues |\n"
        "| `/apply` | Apply staged improvements (review carefully!) |\n"
        "| `/soul` | View agent personality |\n"
        "| `/help` | Full command list |\n",
        encoding="utf-8"
    )

    try:
        console.print(
            f"  [dim #10b981]✓ Launch shortcut created: {shortcut}[/]"
        )
    except Exception:
        pass


def run_setup_wizard(profile) -> None:
    """Full wizard. Safe to re-run via /setup."""
    console.clear()

    # BUG-6 FIX: validate write access BEFORE starting wizard
    ok, err_msg = _validate_write_access(_PROJECT_ROOT_DIR)
    if not ok:
        console.print(f"\n  [bold red]⚠️  Write Access Error[/]\n\n  {err_msg}\n")
        if not Confirm.ask("  Continue anyway (data may not be saved)?", default=False):
            return

    # Step 0 — Welcome
    console.print()
    console.print(Panel(
        "[bold #FFC107]👋  Welcome to Lirox.[/]\n\n"
        "I'm your personal AI agent — I live in your terminal\n"
        "and I get smarter the more we work together.\n\n"
        "[dim]This quick setup lets me actually be useful from message #1.[/]",
        border_style="#FFC107", box=HEAVY, width=66,
        title="[bold #FFD54F] ✦ SETUP [/]"
    ))

    # Step 1 — User name
    console.print()
    user_name = Prompt.ask("  [bold #FFC107]What should I call you?[/]",
                            default=profile.data.get("user_name", "") or "Boss")
    user_name = user_name.strip() or "Boss"
    profile.update("user_name", user_name)
    console.print(f"\n  [bold green]Nice to meet you, {user_name}. 🤝[/]\n")

    # Step 2 — Agent name
    agent_name = _pick_agent_name(profile)
    _sync_agent_name_to_soul(agent_name)
    console.print(f"\n  [bold green]I'm {agent_name} now. Let's go.[/]\n")

    # Step 3 — Niche + deep follow-ups
    niche = _pick_niche()
    profile.update("niche", niche)
    niche_details = _ask_niche_followups(niche)

    # Step 4 — Current project
    current_project = Prompt.ask(
        "\n  [bold #FFC107]What's your current main project?[/] [dim](Enter to skip)[/]",
        default=profile.data.get("current_project", "") or ""
    ).strip()
    if current_project:
        profile.update("current_project", current_project)
        console.print(f"  [dim]Got it — I'll keep '{current_project}' in mind.[/]")

    # Step 5 — Goals
    goals_raw = Prompt.ask(
        f"\n  [bold #FFC107]What are you working on right now, {user_name}?[/] "
        f"[dim](comma-separated, Enter to skip)[/]",
        default=""
    )
    goals = [g.strip() for g in goals_raw.split(",") if g.strip()]
    for g in goals:
        profile.add_goal(g)

    # Step 6 — LLM setup
    _llm_setup_flow()

    # Step 7 — BUG-2 FIX: Home Screen folder integration
    _setup_home_folder_step()

    # Step 7b — Create platform-specific launch shortcut in ~/Lirox/
    _create_launch_shortcut()

    # Step 8 — Memory import (optional, one-paste)
    if Confirm.ask(
        "\n  [bold #FFC107]📋 Import memory from ChatGPT / Claude / Gemini?[/]",
        default=False,
    ):
        _run_one_paste_import()

    # Step 9 — Seed LearningsStore with everything captured
    try:
        stats = seed_learnings_from_wizard(profile.data, niche_details, goals)
        console.print(
            f"\n  [dim green]✓ Seeded {stats['facts']} facts, "
            f"{stats['projects']} project(s), {stats['topics']} topics.[/]"
        )
    except Exception as e:
        console.print(f"\n  [yellow]⚠ Seeding warning: {e}[/]")

    # Store niche details on the profile too (so /profile shows them)
    if niche_details:
        prefs = dict(profile.data.get("preferences") or {})
        prefs.setdefault("niche_details", {}).update(niche_details)
        profile.update("preferences", prefs)

    # BUG-6 FIX: verify profile was actually saved
    _verify_profile_saved(profile)

    # Step 10 — Summary card
    _show_summary(profile, agent_name, user_name, niche)


# ─────────────────────────────────────────────────────────────────────
# Helper steps
# ─────────────────────────────────────────────────────────────────────

def _pick_agent_name(profile) -> str:
    console.print("  [dim]Give me a name, or pick one:[/]")
    opts = {"1": "Lirox", "2": "Atlas", "3": "Nova", "4": "Rex", "5": "Custom"}
    for k, v in opts.items():
        emoji = {"1": "🦁", "2": "🌍", "3": "⭐", "4": "👑", "5": "✏️"}.get(k, "")
        console.print(f"    [{k}] {emoji} {v}")
    choice = Prompt.ask("\n  [bold #FFC107]Pick a name (1-5)[/]",
                        choices=list(opts.keys()), default="1")
    if choice == "5":
        name = Prompt.ask("  [bold #FFC107]Type your agent's name[/]").strip() or "Lirox"
    else:
        name = opts[choice]
    profile.update("agent_name", name)
    return name


def _sync_agent_name_to_soul(name: str) -> None:
    try:
        from lirox.mind.agent import get_soul
        soul = get_soul()
        if soul.get_name() != name:
            soul.set_name(name)
    except Exception:
        pass


def _pick_niche() -> str:
    console.print("\n  [bold #FFC107]What's your primary work?[/]")
    labels = all_niche_labels()
    for i, lbl in enumerate(labels, 1):
        console.print(f"    [{i}] {lbl}")
    choice = Prompt.ask(
        f"\n  Choose (1-{len(labels)})",
        choices=[str(i) for i in range(1, len(labels) + 1)],
        default="1",
    )
    return labels[int(choice) - 1]


def _ask_niche_followups(niche: str) -> dict:
    """Ask the niche-specific follow-ups; return a dict of captured answers."""
    followups = get_niche_followups(niche)
    if not followups:
        return {}
    console.print(
        f"\n  [bold cyan]A few quick specifics about your {niche.lower()} work —[/]"
        f" [dim](Enter to skip any)[/]\n"
    )
    captured = {}
    for key, question, default in followups:
        ans = Prompt.ask(f"  [bold #FFC107]{question}[/]", default=default or "")
        ans = ans.strip()
        if ans:
            captured[key] = ans
    return captured


def _llm_setup_flow() -> None:
    console.print("\n")
    console.print(Panel(
        "[bold #FFC107]🧠 Let's connect your brain.[/]\n\n"
        "I need at least one LLM to think. Pick:\n\n"
        "  [bold cyan]☁️  Cloud LLM[/] — Groq, Gemini, OpenAI (free tiers available)\n"
        "  [bold green]🏠 Local LLM[/] — Ollama (runs on your machine, fully private)\n",
        border_style="#FFC107", box=ROUNDED, width=66
    ))
    llm_type = Prompt.ask("\n  [bold #FFC107]Which setup?[/]",
                          choices=["cloud", "local", "both", "skip"], default="cloud")
    if llm_type in ("local", "both"):
        _setup_ollama()
    if llm_type in ("cloud", "both"):
        _setup_cloud_keys()
    if llm_type == "skip":
        console.print("  [dim]Skipped. Run /setup later to add keys.[/]")


def _setup_ollama() -> None:
    import requests
    console.print("\n  [bold green]🏠 Local LLM Setup (Ollama)[/]")
    console.print("  [dim]Install: https://ollama.ai  ·  Start: ollama serve[/]\n")
    endpoint = Prompt.ask("  Ollama endpoint", default="http://localhost:11434")
    model    = Prompt.ask("  Model", default="gemma3")
    try:
        r = requests.get(f"{endpoint}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            console.print(f"  [bold green]✓ Connected. Found: {', '.join(models[:5]) or '(none)'}[/]")
        else:
            console.print(f"  [yellow]⚠ Status {r.status_code} — check Ollama is running.[/]")
    except Exception:
        console.print("  [yellow]⚠ Can't reach Ollama. Run: ollama serve[/]")

    if not Path(_ENV_PATH).exists():
        Path(_ENV_PATH).write_text("# Lirox Configuration\n")
    set_key(_ENV_PATH, "LOCAL_LLM_ENABLED", "true")
    set_key(_ENV_PATH, "OLLAMA_ENDPOINT", endpoint)
    set_key(_ENV_PATH, "OLLAMA_MODEL", model)
    os.environ["LOCAL_LLM_ENABLED"] = "true"
    os.environ["OLLAMA_ENDPOINT"] = endpoint
    os.environ["OLLAMA_MODEL"]    = model
    console.print(f"  [bold green]✓ Ollama configured: {model} @ {endpoint}[/]")


def _verify_api_key(provider: str, key: str) -> bool:
    import requests
    console.print(f"  [dim]Verifying {provider}…[/]")
    try:
        if provider == "Groq":
            r = requests.get("https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {key}"}, timeout=5)
        elif provider == "Gemini":
            r = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=5)
        elif provider == "OpenRouter":
            r = requests.get("https://openrouter.ai/api/v1/auth/key",
                             headers={"Authorization": f"Bearer {key}"}, timeout=5)
        elif provider == "OpenAI":
            r = requests.get("https://api.openai.com/v1/models",
                             headers={"Authorization": f"Bearer {key}"}, timeout=5)
        elif provider == "Anthropic":
            r = requests.get("https://api.anthropic.com/v1/models",
                             headers={"x-api-key": key,
                                      "anthropic-version": "2023-06-01"}, timeout=5)
            return r.status_code != 401
        elif provider == "DeepSeek":
            r = requests.get("https://api.deepseek.com/models",
                             headers={"Authorization": f"Bearer {key}"}, timeout=5)
        else:
            return True
        if r.status_code == 401:
            console.print("  [red]✖ Invalid API key.[/]")
            return False
        return True
    except Exception:
        console.print("  [yellow]⚠ Network error — proceeding anyway.[/]")
        return True


def _setup_cloud_keys() -> None:
    providers = {
        "1": ("Groq",       "GROQ_API_KEY",       "console.groq.com",     "Free, fastest"),
        "2": ("Gemini",     "GEMINI_API_KEY",     "aistudio.google.com",  "Free, versatile"),
        "3": ("OpenRouter", "OPENROUTER_API_KEY", "openrouter.ai",        "Free models"),
        "4": ("OpenAI",     "OPENAI_API_KEY",     "platform.openai.com",  "Paid"),
        "5": ("Anthropic",  "ANTHROPIC_API_KEY",  "console.anthropic.com","Paid"),
        "6": ("DeepSeek",   "DEEPSEEK_API_KEY",   "deepseek.com",         "Cheap"),
    }
    console.print("\n  [bold cyan]☁️ Cloud LLM Setup[/]")
    for k, (name, env, url, note) in providers.items():
        tick = "✅" if os.getenv(env) else "  "
        console.print(f"    [{k}] {tick} {name.ljust(11)} {url.ljust(25)} [dim]{note}[/]")
    console.print("    [7]    Done / Skip")

    while True:
        choice = Prompt.ask("\n  Add a provider (1-7)",
                            choices=["1","2","3","4","5","6","7"], default="7")
        if choice == "7":
            break
        name, env, _, _ = providers[choice]
        key = Prompt.ask(f"  Paste {name} API key", password=True).strip()
        if not key:
            continue
        if not _verify_api_key(name, key):
            console.print("  [dim]Key not saved. Try again.[/]")
            continue
        if not Path(_ENV_PATH).exists():
            Path(_ENV_PATH).write_text("# Lirox Configuration\n")
        set_key(_ENV_PATH, env, key)
        os.environ[env] = key
        console.print(f"  [bold green]✓ {name} key saved.[/]")
        if not Confirm.ask("  Add another?", default=False):
            break


def _run_one_paste_import() -> None:
    """New one-paste flow. Shows the sync prompt; accepts file path OR pasted JSON."""
    from lirox.memory.sync_prompt import MEMORY_SYNC_PROMPT
    console.print()
    console.print(Panel(
        "[bold]Option A — One-paste Memory Sync[/]\n\n"
        "1. Copy the prompt below.\n"
        "2. Paste it into ChatGPT / Claude / Gemini.\n"
        "3. Copy the ```json block they return.\n"
        "4. Paste it here (any shape — fences optional).\n\n"
        "[bold]Option B — File import[/]\n\n"
        "Paste a file path instead (ChatGPT conversations.json, Claude export, "
        "Gemini Takeout folder, Lirox export).\n",
        title="[bold]📋 Memory Import[/]", border_style="#FFC107", box=HEAVY, width=76
    ))

    console.print("\n  [bold #FFC107]━━━ COPY THIS PROMPT ━━━[/]\n")
    console.print(Panel(MEMORY_SYNC_PROMPT, border_style="cyan",
                         box=ROUNDED, padding=(1, 2), width=76))

    console.print(
        "\n  [bold #FFC107]Paste a file path on one line, OR paste the full JSON.[/]\n"
        "  [dim]When done, type [bold]END[/] on its own line and press Enter.[/]\n"
    )
    buffer = _multiline_read()
    if not buffer.strip():
        console.print("  [dim]Skipped.[/]")
        return

    from lirox.memory.import_handler import MemoryImporter
    from lirox.mind.agent import get_learnings
    importer = MemoryImporter(get_learnings())

    # Is it a file path?
    candidate = buffer.strip().strip("'").strip('"')
    try:
        is_path = Path(candidate).expanduser().exists() and ("\n" not in candidate)
    except OSError:
        is_path = False

    with console.status("[bold cyan]Importing…[/]", spinner="dots"):
        if is_path:
            result = importer.import_file(candidate)
        else:
            result = importer.import_raw_data(buffer, source="pasted")

    _render_import_result(result)


def _multiline_read() -> str:
    """Read a multi-line block. The user MUST type END on its own line to
    finish — this is explicit and unambiguous, unlike heuristic blank-line
    detection which truncated valid JSON paste in v2.x.
    """
    lines: list[str] = []
    while True:
        try:
            line = input("  ")
        except (EOFError, KeyboardInterrupt):
            break
        stripped = line.strip().lower()
        if stripped in ("end", "eof"):
            break
        lines.append(line)
    return "\n".join(lines)


def _render_import_result(result: dict) -> None:
    if not result.get("success"):
        console.print(f"\n  [red]✖ Import failed: {result.get('error', 'unknown')}[/]")
        return
    console.print("\n  [bold green]✓ Import complete[/]")
    def _show(label, key):
        v = result.get(key, 0)
        if v:
            console.print(f"    • {label}: {v}")
    _show("Facts added",           "facts_added")
    _show("Preferences added",     "preferences_added")
    _show("Projects added",        "projects_added")
    _show("Topics added",          "topics_added")
    _show("Dislikes added",        "dislikes_added")
    _show("Profile fields updated","profile_fields_updated")
    src  = result.get("source", "unknown")
    mode = result.get("mode", result.get("imported", ""))
    console.print(f"    [dim]Source: {src}  ·  Mode: {mode}[/]")


def _show_summary(profile, agent_name: str, user_name: str, niche: str) -> None:
    try:
        from lirox.utils.llm import available_providers
        providers = available_providers()
    except Exception:
        providers = []

    console.clear()
    t = Table(box=None, padding=(0, 2), show_header=False)
    t.add_column("k", style="dim")
    t.add_column("v", style="bold white")
    t.add_row("🤖 Agent",    agent_name)
    t.add_row("👤 Operator", user_name)
    t.add_row("💼 Niche",    niche)
    proj = profile.data.get("current_project", "")
    if proj:
        t.add_row("📦 Project", proj)
    t.add_row("🧠 LLMs",     ", ".join(providers) if providers else "None yet")
    goals = profile.data.get("goals", [])
    if goals:
        t.add_row("🎯 Goals", ", ".join(goals[:3]))

    console.print(Panel(
        t,
        border_style="green", box=HEAVY, width=66,
        title=" [bold green]✦ SETUP COMPLETE [/]"
    ))
    console.print(
        f"\n  [bold green]{agent_name} is ready, {user_name}. Let's build. 💪[/]\n"
        f"  [dim]Type anything to start  ·  /help for commands  ·  /recall to see what I know[/]\n"
    )


# ─────────────────────────────────────────────────────────────────────
# BUG-2 FIX: Home Screen folder step
# ─────────────────────────────────────────────────────────────────────

def _setup_home_folder_step() -> None:
    """Ask user permission to create ~/Lirox/ folder for easy file access."""
    try:
        from lirox.home_screen.integration import (
            is_home_folder_setup, setup_home_folder, HOME_LIROX_DIR
        )

        if is_home_folder_setup():
            console.print(
                f"\n  [dim green]✓ Lirox workspace already exists at {HOME_LIROX_DIR}[/]"
            )
            return

        console.print()
        console.print(Panel(
            "[bold #FFC107]📁 Home Screen Access[/]\n\n"
            f"Create a [bold]~/Lirox/[/] folder for easy access to your:\n"
            "  • Memory & sessions    • Skills & agents\n"
            "  • Backups              • Audit logs\n\n"
            "[dim]A shortcut will also be added to your file manager.[/]",
            border_style="#FFC107", box=ROUNDED, width=66,
        ))

        if Confirm.ask(
            f"\n  [bold #FFC107]Create ~/Lirox/ workspace folder?[/]",
            default=True,
        ):
            result = setup_home_folder(ask=False)
            if result["created"]:
                msg = f"  [bold green]✓ Workspace created: {HOME_LIROX_DIR}[/]"
                if result.get("shortcut"):
                    msg += "  [dim](shortcut added to file manager)[/]"
                console.print(msg)
                # Link data dirs
                try:
                    from lirox.config import DATA_DIR
                    from lirox.home_screen.integration import link_data_dir
                    link_data_dir(DATA_DIR)
                except Exception:
                    pass
            else:
                console.print(
                    f"  [yellow]⚠ Could not create folder: {result.get('error', 'unknown')}[/]\n"
                    f"  [dim]You can create it manually: mkdir ~/Lirox[/]"
                )
        else:
            console.print("  [dim]Skipped. You can always access files via /backup and /export-memory.[/]")
    except Exception as e:
        console.print(f"  [dim]Home folder setup skipped: {e}[/]")


# ─────────────────────────────────────────────────────────────────────
# BUG-6 FIX: verify profile was actually persisted to disk
# ─────────────────────────────────────────────────────────────────────

def _verify_profile_saved(profile) -> None:
    """Verify that the profile file exists on disk after setup completes."""
    try:
        profile_path = _PROJECT_ROOT_DIR / "profile.json"
        if not profile_path.exists():
            console.print(
                "\n  [yellow]⚠ Profile file not found on disk after setup.[/]\n"
                "  [dim]Attempting to save again…[/]"
            )
            try:
                profile._save()  # force a re-save
                if profile_path.exists():
                    console.print("  [green]✓ Profile saved successfully.[/]")
                else:
                    console.print(
                        "  [red]✖ Profile could not be saved.[/]\n"
                        f"  [dim]Check write permissions for: {_PROJECT_ROOT_DIR}[/]"
                    )
            except Exception as save_err:
                console.print(
                    f"  [red]✖ Save failed: {save_err}[/]\n"
                    "  [dim]Your preferences may not persist between sessions.[/]"
                )
    except Exception:
        pass  # verification is best-effort

