"""Lirox v2.1 — Advanced First-Run Onboarding Wizard"""
import os
import json
from pathlib import Path
from rich.panel import Panel
from rich.box import ROUNDED, HEAVY
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
from lirox.ui.display import console, CLR_LIROX, CLR_SUCCESS, CLR_DIM, CLR_ACCENT
from rich.prompt import Prompt, Confirm
from dotenv import set_key

_PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT_DIR / ".env")


def run_setup_wizard(profile):
    """Advanced first-run onboarding — warm, personal, thorough."""
    console.clear()

    # ── Step 0: Warm Welcome ──────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold #FFC107]👋 Hey there! Welcome to Lirox.[/]\n\n"
        "I'm your personal AI agent — I live in your terminal\n"
        "and I get smarter the more we work together.\n\n"
        "[dim]Let me get to know you so I can be actually useful.[/]",
        border_style="#FFC107", box=HEAVY, width=64,
        title="[bold #FFD54F] ✦ FIRST RUN [/]"
    ))

    # ── Step 1: Learn the user's name ─────────────────────────────────────
    console.print()
    user_name = Prompt.ask("  [bold #FFC107]What should I call you?[/]")
    if not user_name.strip():
        user_name = "Boss"
    profile.update("user_name", user_name.strip())

    console.print(f"\n  [bold green]Nice to meet you, {user_name}! 🤝[/]\n")

    # ── Step 2: Name the agent ────────────────────────────────────────────
    console.print("  [dim]You can give me a custom name, or pick one:[/]")
    agent_options = {"1": "Lirox", "2": "Atlas", "3": "Nova", "4": "Rex", "5": "Custom"}
    for k, v in agent_options.items():
        emoji = {"1": "🦁", "2": "🌍", "3": "⭐", "4": "👑", "5": "✏️"}.get(k, "")
        console.print(f"    [{k}] {emoji} {v}")

    choice = Prompt.ask("\n  [bold #FFC107]Pick a name (1-5)[/]",
                        choices=["1","2","3","4","5"], default="1")
    if choice == "5":
        custom = Prompt.ask("  [bold #FFC107]Type your agent's name[/]")
        agent_name = custom.strip() or "Lirox"
    else:
        agent_name = agent_options[choice]
    profile.update("agent_name", agent_name)
    console.print(f"\n  [bold green]I'm {agent_name} now. Let's go. 🚀[/]\n")

    # ── Step 3: What do you do? ───────────────────────────────────────────
    console.print("  [bold #FFC107]What's your primary work?[/]")
    niche_options = {
        "1": "Developer", "2": "Founder / CEO", "3": "Content Creator",
        "4": "Researcher", "5": "Student", "6": "Data Scientist",
        "7": "Designer", "8": "Trader / Finance", "9": "Writer", "10": "Other"
    }
    for k, v in niche_options.items():
        console.print(f"    [{k}] {v}")

    niche_choice = Prompt.ask("\n  Choose (1-10)", choices=[str(i) for i in range(1, 11)], default="1")
    niche = niche_options[niche_choice]
    profile.update("niche", niche)

    # ── Step 4: What are your goals? ──────────────────────────────────────
    console.print(f"\n  [bold #FFC107]What are you working on right now, {user_name}?[/]")
    console.print("  [dim]Tell me your current focus — I'll remember and adapt. (or press Enter to skip)[/]")
    goals_input = Prompt.ask("  ", default="")
    if goals_input.strip():
        for goal in goals_input.split(","):
            g = goal.strip()
            if g:
                profile.add_goal(g)

    # ── Step 5: LLM Setup ─────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold #FFC107]🧠 Let's connect your brain.[/]\n\n"
        "I need at least one LLM to think.\n"
        "You have two options:\n\n"
        "  [bold cyan]☁️  Cloud LLM[/] — Groq, Gemini, OpenAI (free tiers available)\n"
        "  [bold green]🏠 Local LLM[/] — Ollama (runs on your machine, fully private)\n",
        border_style="#FFC107", box=ROUNDED, width=64
    ))

    llm_type = Prompt.ask("\n  [bold #FFC107]Which setup?[/]",
                          choices=["cloud", "local", "both", "skip"], default="cloud")

    if llm_type in ("local", "both"):
        _setup_ollama()

    if llm_type in ("cloud", "both"):
        _setup_cloud_keys()

    if llm_type == "skip":
        console.print("  [dim]Skipped. You can add keys later with /setup[/]")

    # ── Step 6: Memory Import ─────────────────────────────────────────────
    console.print()
    wants_import = Confirm.ask(
        f"  [bold #FFC107]🧠 Want to import your memory from ChatGPT / Claude / Gemini?[/]",
        default=False
    )

    if wants_import:
        _show_memory_import_prompt(profile, user_name, agent_name)

    # ── Step 7: Summary ───────────────────────────────────────────────────
    console.clear()
    providers = []
    from lirox.utils.llm import available_providers
    providers = available_providers()

    summary = Table(box=None, padding=(0, 2), show_header=False)
    summary.add_column("Key", style="dim")
    summary.add_column("Value", style="bold white")
    summary.add_row("🤖 Agent", agent_name)
    summary.add_row("👤 Operator", user_name)
    summary.add_row("💼 Niche", niche)
    summary.add_row("🧠 LLMs", ", ".join(providers) if providers else "None yet")
    summary.add_row("🎯 Goals", ", ".join(profile.data.get("goals", [])) or "Not set")

    console.print(Panel(
        summary,
        border_style="green", box=HEAVY, width=64,
        title=" [bold green]✦ SETUP COMPLETE [/] "
    ))

    console.print(f"\n  [bold green]{agent_name} is ready, {user_name}. Let's build something. 💪[/]\n")
    console.print(f"  [dim]Type anything to start · /help for commands · /setup to reconfigure[/]\n")


def _setup_ollama():
    """Configure Ollama local LLM."""
    console.print("\n  [bold green]🏠 Local LLM Setup (Ollama)[/]")
    console.print("  [dim]Make sure Ollama is installed: https://ollama.ai[/]")
    console.print("  [dim]And running: ollama serve[/]\n")

    endpoint = Prompt.ask("  Ollama endpoint", default="http://localhost:11434")
    model = Prompt.ask("  Model to use", default="gemma3")

    # Test connection
    console.print("  [dim]Testing connection...[/]")
    try:
        import requests
        r = requests.get(f"{endpoint}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            console.print(f"  [bold green]✓ Connected! Available models: {', '.join(models[:5])}[/]")
        else:
            console.print(f"  [yellow]⚠ Server responded but status {r.status_code}[/]")
    except Exception:
        console.print("  [yellow]⚠ Can't reach Ollama. Make sure it's running: ollama serve[/]")

    # Save to .env
    if not Path(_ENV_PATH).exists():
        Path(_ENV_PATH).write_text("# Lirox Configuration\n")
    set_key(_ENV_PATH, "LOCAL_LLM_ENABLED", "true")
    set_key(_ENV_PATH, "OLLAMA_ENDPOINT", endpoint)
    set_key(_ENV_PATH, "OLLAMA_MODEL", model)
    os.environ["LOCAL_LLM_ENABLED"] = "true"
    os.environ["OLLAMA_ENDPOINT"] = endpoint
    os.environ["OLLAMA_MODEL"] = model
    console.print(f"  [bold green]✓ Ollama configured: {model} @ {endpoint}[/]\n")


def _setup_cloud_keys():
    """Configure cloud LLM API keys."""
    provider_options = {
        "1": ("Groq", "GROQ_API_KEY", "console.groq.com", "Free, fastest"),
        "2": ("Gemini", "GEMINI_API_KEY", "aistudio.google.com", "Free, versatile"),
        "3": ("OpenRouter", "OPENROUTER_API_KEY", "openrouter.ai", "Free models available"),
        "4": ("OpenAI", "OPENAI_API_KEY", "platform.openai.com", "Paid"),
        "5": ("Anthropic", "ANTHROPIC_API_KEY", "console.anthropic.com", "Paid"),
        "6": ("DeepSeek", "DEEPSEEK_API_KEY", "deepseek.com", "Cheap"),
    }

    console.print("\n  [bold cyan]☁️ Cloud LLM Setup[/]")
    for k, (name, env_key, url, note) in provider_options.items():
        status = "✅" if os.getenv(env_key) else "  "
        console.print(f"    [{k}] {status} {name.ljust(12)} {url.ljust(25)} [dim]{note}[/]")
    console.print("    [7]    Done / Skip")

    while True:
        choice = Prompt.ask("\n  Add a provider (1-7)", choices=["1","2","3","4","5","6","7"], default="7")
        if choice == "7":
            break
        name, env_key, url, _ = provider_options[choice]
        key = Prompt.ask(f"  Paste {name} API key", password=True)
        if key and key.strip():
            if not Path(_ENV_PATH).exists():
                Path(_ENV_PATH).write_text("# Lirox Configuration\n")
            set_key(_ENV_PATH, env_key, key.strip())
            os.environ[env_key] = key.strip()
            console.print(f"  [bold green]✓ {name} key saved[/]")
        if not Confirm.ask("  Add another?", default=False):
            break


def _show_memory_import_prompt(profile, user_name, agent_name):
    """Show the prompt the user should paste into ChatGPT/Claude/Gemini to export their memory."""
    console.print()

    export_prompt = f"""You are helping me export my preferences, context, and learned facts to a new AI assistant called {agent_name}.

Please analyze ALL of our conversation history and your memory of me, then output a JSON block with this exact structure:

```json
{{
  "user_name": "{user_name}",
  "profession": "your best guess of my profession",
  "interests": ["list", "of", "my", "key", "interests"],
  "communication_style": "how I prefer to communicate (direct/detailed/casual/formal)",
  "goals": ["my", "active", "goals", "or", "projects"],
  "technical_skills": ["languages", "frameworks", "tools", "I", "use"],
  "preferences": {{
    "tone": "direct or detailed or casual",
    "output_format": "what format I usually want (code/analysis/brief)",
    "topics_i_care_about": ["list"]
  }},
  "learned_facts": [
    "fact 1 about me",
    "fact 2 about me",
    "up to 30 facts you know about me"
  ]
}}
```

Be thorough. Include everything you know about me — my work, preferences, patterns, tools, and context. This will help my new agent {agent_name} understand me from day one."""

    console.print(Panel(
        "[bold #FFC107]📋 Memory Export Prompt[/]\n\n"
        "Copy the prompt below and paste it into:\n"
        "  • ChatGPT (chat.openai.com)\n"
        "  • Claude (claude.ai)\n"
        "  • Gemini (gemini.google.com)\n\n"
        "Then copy the JSON response and paste it back here.\n",
        border_style="#FFC107", box=ROUNDED, width=70
    ))

    # Show the prompt in a copyable format
    console.print(Panel(
        export_prompt,
        border_style="cyan", title="[cyan] COPY THIS PROMPT [/]", width=70
    ))

    console.print("\n  [bold #FFC107]After you get the JSON response, paste it below.[/]")
    console.print("  [dim](Press Enter twice when done, or type 'skip' to skip)[/]\n")

    lines = []
    while True:
        try:
            line = input("  ")
            if line.strip().lower() == "skip":
                console.print("  [dim]Skipped memory import.[/]")
                return
            lines.append(line)
            # Detect end of JSON
            full = "\n".join(lines)
            if full.strip().endswith("}"):
                # Try parsing
                import re
                json_match = re.search(r'\{.*\}', full, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        _import_memory_data(profile, data)
                        return
                    except json.JSONDecodeError:
                        continue
        except EOFError:
            break

    # Try one final parse
    full = "\n".join(lines)
    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', full, re.DOTALL)
    if not json_match:
        json_match = re.search(r'\{.*\}', full, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1) if '```' in full else json_match.group())
            _import_memory_data(profile, data)
        except Exception:
            console.print("  [yellow]⚠ Couldn't parse the JSON. You can try again with /import-memory[/]")
    else:
        console.print("  [dim]No JSON detected. Skipping.[/]")


def _import_memory_data(profile, data: dict):
    """Import parsed memory JSON into the user profile."""
    imported = 0

    if data.get("profession"):
        profile.update("profession", data["profession"])
        imported += 1

    if data.get("communication_style"):
        profile.update("tone", data["communication_style"])
        imported += 1

    for goal in data.get("goals", []):
        if goal:
            profile.add_goal(str(goal))
            imported += 1

    for fact in data.get("learned_facts", []):
        if fact:
            profile.add_learned_fact(str(fact))
            imported += 1

    for interest in data.get("interests", []):
        if interest:
            profile.add_learned_preference("interests", str(interest))
            imported += 1

    for skill in data.get("technical_skills", []):
        if skill:
            profile.add_learned_preference("technical_skills", str(skill))
            imported += 1

    prefs = data.get("preferences", {})
    if isinstance(prefs, dict):
        for k, v in prefs.items():
            if isinstance(v, list):
                for item in v:
                    profile.add_learned_preference(k, str(item))
                    imported += 1
            elif v:
                profile.update(f"pref_{k}", v)
                imported += 1

    console.print(f"\n  [bold green]✅ Imported {imported} items into your profile![/]")
    console.print(f"  [dim]{profile.data.get('agent_name', 'Lirox')} now knows you better from day one.[/]\n")
