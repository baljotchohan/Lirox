"""Lirox v2.0.0 — Setup Wizard

Simplified setup wizard that doesn't depend on mind/soul modules.
Collects: name, agent name, niche, LLM keys.
"""
from __future__ import annotations

import os
from pathlib import Path

from rich.box import HEAVY, ROUNDED
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from lirox.ui.display import console

_PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT_DIR / ".env")

_NICHES = [
    "Software Development",
    "Data Science / ML",
    "Business / Entrepreneurship",
    "Design / Creative",
    "Writing / Content",
    "Research / Academia",
    "DevOps / Infrastructure",
    "Finance / Investing",
    "Marketing / Growth",
    "Generalist",
]


def run_setup_wizard(profile) -> None:
    """Full setup wizard. Safe to re-run via /setup."""
    console.clear()

    console.print()
    console.print(Panel(
        "[bold #FFC107]👋  Welcome to Lirox v2.0.0[/]\n\n"
        "I'm your personal AI agent — I live in your terminal\n"
        "and I get smarter the more we work together.\n\n"
        "[dim]This quick setup lets me be useful from message #1.[/]",
        border_style="#FFC107", box=HEAVY, width=66,
        title="[bold #FFD54F] ✦ SETUP [/]"
    ))

    # Step 1 — User name
    console.print()
    user_name = Prompt.ask(
        "  [bold #FFC107]What should I call you?[/]",
        default=profile.data.get("user_name", "") or "Operator"
    )
    user_name = user_name.strip() or "Operator"
    profile.update("user_name", user_name)
    console.print(f"\n  [bold green]Nice to meet you, {user_name}. 🤝[/]\n")

    # Step 2 — Agent name
    agent_name = _pick_agent_name(profile)
    console.print(f"\n  [bold green]I'm {agent_name} now. Let's go.[/]\n")

    # Step 3 — Niche
    niche = _pick_niche()
    profile.update("niche", niche)

    # Step 4 — Current project
    current_project = Prompt.ask(
        "\n  [bold #FFC107]What's your current main project?[/] [dim](Enter to skip)[/]",
        default=profile.data.get("current_project", "") or ""
    ).strip()
    if current_project:
        profile.update("current_project", current_project)

    # Step 5 — Goals
    goals_raw = Prompt.ask(
        f"\n  [bold #FFC107]What are you working on, {user_name}?[/] "
        f"[dim](comma-separated, Enter to skip)[/]",
        default=""
    )
    goals = [g.strip() for g in goals_raw.split(",") if g.strip()]
    for g in goals:
        profile.add_goal(g)

    # Step 6 — LLM setup
    _llm_setup_flow()

    # Summary
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


def _pick_niche() -> str:
    console.print("\n  [bold #FFC107]What's your primary work?[/]")
    for i, label in enumerate(_NICHES, 1):
        console.print(f"    [{i}] {label}")
    choice = Prompt.ask(
        f"\n  Choose (1-{len(_NICHES)})",
        choices=[str(i) for i in range(1, len(_NICHES) + 1)],
        default="1",
    )
    return _NICHES[int(choice) - 1]


def _llm_setup_flow() -> None:
    console.print("\n")
    console.print(Panel(
        "[bold #FFC107]🧠 Let's connect your brain.[/]\n\n"
        "I need at least one LLM to think. Options:\n\n"
        "  [bold cyan]☁️  Cloud LLM[/] — Groq (free), Gemini (free), OpenAI, Anthropic\n"
        "  [bold green]🏠 Local LLM[/]  — Ollama (fully private, runs on your machine)\n",
        border_style="#FFC107", box=ROUNDED, width=66
    ))
    llm_type = Prompt.ask(
        "\n  [bold #FFC107]Which setup?[/]",
        choices=["cloud", "local", "both", "skip"], default="cloud"
    )
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
    model    = Prompt.ask("  Model", default="llama3")
    try:
        r = requests.get(f"{endpoint}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            console.print(
                f"  [bold green]✓ Connected. Models: {', '.join(models[:5]) or '(none)'}[/]"
            )
        else:
            console.print(f"  [yellow]⚠ Status {r.status_code}[/]")
    except Exception:
        console.print("  [yellow]⚠ Can't reach Ollama. Run: ollama serve[/]")

    _write_env("LOCAL_LLM_ENABLED", "true")
    _write_env("OLLAMA_ENDPOINT", endpoint)
    _write_env("OLLAMA_MODEL", model)
    os.environ["LOCAL_LLM_ENABLED"] = "true"
    os.environ["OLLAMA_ENDPOINT"]   = endpoint
    os.environ["OLLAMA_MODEL"]      = model
    console.print(f"  [bold green]✓ Ollama configured: {model} @ {endpoint}[/]")


def _setup_cloud_keys() -> None:
    providers = {
        "1": ("Groq",       "GROQ_API_KEY",       "console.groq.com",     "Free, fastest"),
        "2": ("Gemini",     "GEMINI_API_KEY",      "aistudio.google.com",  "Free, versatile"),
        "3": ("OpenRouter", "OPENROUTER_API_KEY",  "openrouter.ai",        "Free models"),
        "4": ("OpenAI",     "OPENAI_API_KEY",      "platform.openai.com",  "Paid"),
        "5": ("Anthropic",  "ANTHROPIC_API_KEY",   "console.anthropic.com","Paid"),
    }
    console.print("\n  [bold cyan]☁️  Cloud LLM Setup[/]")
    for k, (name, env, url, note) in providers.items():
        tick = "✅" if os.getenv(env) else "  "
        console.print(f"    [{k}] {tick} {name.ljust(11)} {url.ljust(28)} [dim]{note}[/]")
    console.print("    [6]    Done / Skip")

    while True:
        choice = Prompt.ask("\n  Add a provider (1-6)",
                            choices=["1", "2", "3", "4", "5", "6"], default="6")
        if choice == "6":
            break
        name, env, _, _ = providers[choice]
        key = Prompt.ask(f"  Paste {name} API key", password=True).strip()
        if not key:
            continue
        _write_env(env, key)
        os.environ[env] = key
        console.print(f"  [bold green]✓ {name} key saved.[/]")
        if not Confirm.ask("  Add another?", default=False):
            break


def _write_env(key: str, value: str) -> None:
    """Write or update a key in the .env file."""
    try:
        from dotenv import set_key
        if not Path(_ENV_PATH).exists():
            Path(_ENV_PATH).write_text("# Lirox Configuration\n", encoding="utf-8")
        set_key(_ENV_PATH, key, value)
    except Exception:
        pass


def _show_summary(profile, agent_name: str, user_name: str, niche: str) -> None:
    from rich.table import Table
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
    t.add_row("🧠 LLMs", ", ".join(providers) if providers else "None yet")
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
        f"  [dim]Type anything to start  ·  /help for all commands[/]\n"
    )
