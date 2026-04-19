"""Lirox v1.1 — Setup Wizard

Steps:
  1. Welcome + operator name
  2. Agent name
  3. Work/niche
  4. Current project
  5. Goals
  6. LLM setup (local + cloud)
  7. Summary card
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import set_key
from rich.box import ROUNDED, HEAVY, SIMPLE, DOUBLE
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from lirox.ui.display import console

_PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT_DIR / ".env")


def _validate_write_access(directory: Path) -> tuple:
    test_file = directory / ".lirox_write_test"
    try:
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return True, ""
    except PermissionError:
        return False, f"No write permission to: {directory}"
    except OSError as e:
        return False, f"Cannot write to {directory}: {e}"


def run_setup_wizard(profile) -> None:
    console.clear()

    ok, err_msg = _validate_write_access(_PROJECT_ROOT_DIR)
    if not ok:
        console.print(f"\n  [bold red]⚠️  Write Access Error[/]\n\n  {err_msg}\n")
        if not Confirm.ask("  Continue anyway?", default=False):
            return

    # Step 0 — Welcome
    console.print()
    console.print(Panel(
        "[bold #FFC107]👋  Welcome to Lirox.[/]\n\n"
        "I'm your personal AI agent — I live in your terminal\n"
        "and I get smarter the more we work together.\n\n"
        "[dim]This quick setup lets me be useful from message #1.[/]",
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

    # Step 3 — Niche
    niche = _pick_niche()
    profile.update("niche", niche)

    # Step 3b — Profession
    profession = Prompt.ask(
        "\n  [bold #FFC107]What's your role/title?[/] [dim](Enter to skip)[/]",
        default=profile.data.get("profession", "") or ""
    ).strip()
    if profession:
        profile.update("profession", profession)

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

    # Step 6 — Seed learnings from what we just captured
    try:
        from lirox.mind.learnings import LearningsStore
        store = LearningsStore()
        seeded = 0
        if user_name and user_name != "Boss":
            store.add_fact(f"User's name is {user_name}", confidence=1.0, source="setup")
            seeded += 1
        if niche:
            store.add_fact(f"Works in {niche}", confidence=0.95, source="setup")
            store.bump_topic(niche.lower())
            seeded += 1
        if profession:
            store.add_fact(f"Role: {profession}", confidence=0.95, source="setup")
            seeded += 1
        if current_project:
            store.add_project(current_project, description="Current main project")
            seeded += 1
        for g in goals:
            store.add_fact(f"Goal: {g}", confidence=0.9, source="setup")
            seeded += 1
        if seeded > 0:
            console.print(f"\n  [dim green]✓ Seeded {seeded} facts from setup.[/]")
    except Exception as e:
        console.print(f"\n  [yellow]⚠ Seeding warning: {e}[/]")

    # Step 7 — LLM setup
    _llm_setup_flow()

    # Step 8 — Memory import (optional, one-paste)
    if Confirm.ask(
        "\n  [bold #FFC107]📋 Import memory from ChatGPT / Claude / Gemini?[/]",
        default=False,
    ):
        _run_one_paste_import()

    # Verify profile saved
    _verify_profile_saved(profile)

    # Step 9 — Summary card
    _show_summary(profile, agent_name, user_name, niche)


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


_NICHE_OPTIONS = [
    "Software Development",
    "AI / Machine Learning",
    "Data Science",
    "DevOps / Cloud",
    "Product Management",
    "Design / UX",
    "Marketing / Growth",
    "Finance / Trading",
    "Content Creation",
    "Research / Academia",
    "Founder / Startup",
    "Student",
    "Other",
]


def _pick_niche() -> str:
    console.print("\n  [bold #FFC107]What's your primary work?[/]")
    for i, lbl in enumerate(_NICHE_OPTIONS, 1):
        console.print(f"    [{i}] {lbl}")
    choice = Prompt.ask(
        f"\n  Choose (1-{len(_NICHE_OPTIONS)})",
        choices=[str(i) for i in range(1, len(_NICHE_OPTIONS) + 1)],
        default="1",
    )
    selected = _NICHE_OPTIONS[int(choice) - 1]
    if selected == "Other":
        selected = Prompt.ask("  [bold #FFC107]Describe your work[/]").strip() or "General"
    return selected


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
    detection which truncated valid JSON paste in earlier versions.
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


def _verify_profile_saved(profile) -> None:
    try:
        profile_path = _PROJECT_ROOT_DIR / "profile.json"
        if not profile_path.exists():
            console.print("\n  [yellow]⚠ Profile file not found. Saving…[/]")
            try:
                profile.save()
                if profile_path.exists():
                    console.print("  [green]✓ Profile saved.[/]")
                else:
                    console.print(f"  [red]✖ Could not save profile to {_PROJECT_ROOT_DIR}[/]")
            except Exception as e:
                console.print(f"  [red]✖ Save failed: {e}[/]")
    except Exception:
        pass
