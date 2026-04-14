"""Lirox v0.5 — Mind Agent Setup Wizard"""
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
    # Sync the chosen name to the living soul immediately
    try:
        from lirox.mind.agent import get_soul
        soul = get_soul()
        soul.set_name(agent_name)
    except Exception:
        pass  # best-effort — profile already saved
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

    # ── Step: Current main project ─────────────────────────────────────────
    console.print()
    current_project = Prompt.ask(
        "  [bold #FFC107]What's your current main project?[/] [dim](Enter to skip)[/]",
        default=""
    )
    if current_project.strip():
        profile.update("current_project", current_project.strip())
        console.print(f"  [dim]Got it — I'll keep {current_project.strip()} in mind.[/]\n")

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

    # ── Step 6: Memory Management ─────────────────────────────────────────
    console.print()
    
    # If already setup, allow exporting current memory first
    if profile.is_setup():
        if Confirm.ask("  [bold #FFC107]📦 Already setup. Want to export your current memory first?[/]", default=False):
            from lirox.utils.memory_utils import export_full_memory
            with console.status("[bold cyan]Exporting...[/]"):
                path = export_full_memory()
            console.print(f"  [bold green]✓ Exported to: {path}[/]\n")

    wants_import = Confirm.ask(
        f"  [bold #FFC107]🧠 Want to import memory from ChatGPT / Claude / Gemini?[/]",
        default=False
    )

    if wants_import:
        _run_memory_import(profile)

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


def _verify_api_key(provider_name: str, api_key: str) -> bool:
    """Verify if the provided API key is valid using the provider's REST API."""
    import requests
    console.print(f"  [dim]Verifying {provider_name} API key...[/]")
    try:
        if provider_name == "Groq":
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        elif provider_name == "Gemini":
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=5)
        elif provider_name == "OpenRouter":
            r = requests.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        elif provider_name == "OpenAI":
            r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        elif provider_name == "Anthropic":
            r = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                timeout=5,
            )
            # ONLY 401 means invalid key. 403 = valid key, wrong permissions.
            if r.status_code == 401:
                console.print("  [bold red]✖ Invalid API key. Verification failed.[/]")
                return False
            return True
        elif provider_name == "DeepSeek":
            r = requests.get("https://api.deepseek.com/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        else:
            return True

        if r.status_code == 401:
            console.print("  [bold red]✖ Invalid API key. Verification failed.[/]")
            return False
            
        return True
    except Exception:
        console.print("  [yellow]⚠ Network error during verification, proceeding anyway.[/]")
        return True


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
            if _verify_api_key(name, key.strip()):
                if not Path(_ENV_PATH).exists():
                    Path(_ENV_PATH).write_text("# Lirox Configuration\n")
                set_key(_ENV_PATH, env_key, key.strip())
                os.environ[env_key] = key.strip()
                console.print(f"  [bold green]✓ {name} key saved[/]")
            else:
                console.print("  [dim]Key was not saved. Please try again.[/]")
                continue
        if not Confirm.ask("  Add another?", default=False):
            break


def _run_memory_import(profile):
    """Interactively import memory from external sources."""
    console.print()
    console.print(Panel(
        "[bold #FFC107]📋 Memory Import[/]\n\n"
        "I can learn from your history with other AIs. Here's how to get your files:\n\n"
        "  [bold]ChatGPT[/]: Settings → Data Controls → Export Data (you'll get a .zip with [italic]conversations.json[/])\n"
        "  [bold]Claude[/]: Settings → Account → Export Data (you'll get a [italic]claude_conversations.json[/])\n"
        "  [bold]Gemini[/]: takeout.google.com → Select 'Gemini' → Export (provide the [italic]Takeout[/] folder path)\n\n"
        "Supported: ChatGPT (JSON), Claude (JSON), or plain .txt/.md files.\n"
        "You can also provide a previously exported [bold]Lirox Memory[/] file.\n",
        border_style="#FFC107", box=ROUNDED, width=64
    ))
    
    while True:
        file_path = Prompt.ask("  [bold #FFC107]Path to export file/folder[/] [dim](or Enter to skip)[/]", default="")
        if not file_path:
            return

        # Clean path (handle quotes if user pasted path with quotes)
        path_str = file_path.strip().strip("'").strip('"')
        path = Path(path_str)

        if not path.exists():
            console.print(f"  [bold red]✖ File not found:[/] [dim]{path_str}[/]")
            console.print("  [dim]Tip: Drag and drop the file into your terminal to paste the path.[/]\n")
            if not Confirm.ask("  Try again?", default=True):
                return
            continue
        break

    from lirox.memory.import_handler import MemoryImporter
    from lirox.mind.agent import get_learnings
    
    with console.status("[bold cyan]Importing and analyzing memory...[/]", spinner="dots"):
        importer = MemoryImporter(get_learnings())
        res = importer.import_file(str(path))
        
    if "error" in res:
        console.print(f"  [red]✖ Import failed: {res['error']}[/]")
    else:
        console.print(f"\n  [bold green]✓ Success![/]")
        count = res.get('imported', 0)
        source = res.get('source', 'unknown')
        facts = res.get('facts_added', 0)
        
        if res.get("is_full"):
             console.print(f"  [dim]Restored full Lirox profile and {facts} facts.[/]")
        else:
             console.print(f"  [dim]Imported {count} messages from {source}.[/]")
             console.print(f"  [dim]Extracted {facts} facts and {res.get('topics_added', 0)} topics.[/]\n")
        
        console.print("  [dim]Identity synced. My understanding of you is now significantly deeper.[/]\n")

