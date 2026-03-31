import os
from pathlib import Path
from lirox.ui.display import console, Panel, ROUNDED
from rich.prompt import Prompt
from dotenv import set_key

# Anchor .env path to project root (same logic as config.py)
_PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT_DIR / ".env")


def run_setup_wizard(profile):
    """First-time setup: collect user identity and goals."""
    console.clear()
    console.print(Panel(
        "Welcome to Lirox. Let's set you up.",
        border_style="agent", box=ROUNDED, width=60
    ))
    console.print("\n  This takes 60 seconds. Your agent will remember everything")
    console.print("  you tell it — now and in every future session.\n")

    # Step 1 - Agent Name
    agent_name = Prompt.ask(
        "\n  What do you want to call your AI agent?\n  (e.g. Atlas, Nova, Rex, Iris)",
        default="Lirox"
    )
    profile.update("agent_name", agent_name)

    # Step 2 - User Name
    user_name = Prompt.ask("\n  What's your name?")
    profile.update("user_name", user_name)

    # Step 3 - Niche
    niche = Prompt.ask(
        "\n  What do you do? (your niche, profession, or focus)\n  e.g. YouTube content creator, founder, developer"
    )
    profile.update("niche", niche)

    # Step 4 - Goals
    console.print("\n  What are your top 3 goals right now?")
    for i in range(1, 4):
        goal = Prompt.ask(f"  Goal {i} (leave blank to skip)", default="")
        if goal:
            profile.add_goal(goal)

    # Step 5 - Tone
    tone_options = {
        "1": ("Direct",   "No fluff. Get to the point fast."),
        "2": ("Friendly", "Warm, encouraging, supportive."),
        "3": ("Formal",   "Professional tone at all times."),
        "4": ("Casual",   "Relaxed and conversational.")
    }

    console.print("\n  How should your agent talk to you?\n")
    for k, (name, desc) in tone_options.items():
        console.print(f"  [{k}] {name.ljust(10)} {desc}")

    tone_choice = Prompt.ask("\n  Choose (1-4)", choices=["1", "2", "3", "4"], default="1")
    profile.update("tone", tone_options[tone_choice][0].lower())

    # Step 6 - Context
    context = Prompt.ask("\n  Tell your agent anything important about you (optional)", default="")
    if context:
        profile.update("user_context", context)

    # API Keys check — always run for new users
    check_api_keys(force=True)

    console.clear()
    console.print(Panel(
        f"✓ Profile saved\n\n"
        f"Agent:  {agent_name}\n"
        f"User:   {user_name}\n"
        f"Niche:  {niche}\n"
        f"Tone:   {tone_options[tone_choice][0]}\n\n"
        f"{agent_name} is ready. Type anything to begin.",
        border_style="success", box=ROUNDED, title=" Setup Complete "
    ))


def check_api_keys(force=False):
    """
    Integrated API key setup.
    - If force=True: always prompt (used during first-run setup).
    - If force=False: only prompt if NO keys are configured yet.
    """
    provider_options = {
        "1": ("Gemini",      "GEMINI_API_KEY",      "aistudio.google.com  — FREE tier available"),
        "2": ("Groq",        "GROQ_API_KEY",        "console.groq.com     — FREE tier available"),
        "3": ("OpenRouter",  "OPENROUTER_API_KEY",  "openrouter.ai        — FREE models available"),
        "4": ("OpenAI",      "OPENAI_API_KEY",      "platform.openai.com  — Paid"),
        "5": ("DeepSeek",    "DEEPSEEK_API_KEY",    "platform.deepseek.com — Very cheap"),
        "6": ("NVIDIA NIM",  "NVIDIA_API_KEY",      "build.nvidia.com     — FREE tier available"),
    }

    existing = [p for _, (_, env_key, _) in provider_options.items() if os.getenv(env_key)]

    if not force and existing:
        # Already configured — no need to prompt
        return

    console.print("\n" + "─" * 60)
    if not existing:
        console.print("  ⚠  No API keys found. Add at least one key to use Lirox.")
    else:
        console.print(f"  ✓  {len(existing)} provider(s) already configured.")
        console.print("  You can add more keys now, or press Enter to continue.")
    console.print("─" * 60 + "\n")

    console.print("  Recommended free options: Groq (#2) or Gemini (#1)\n")
    for k, (name, env_key, url) in provider_options.items():
        status = " ✓" if os.getenv(env_key) else "  "
        console.print(f"  [{k}]{status} {name.ljust(12)} {url}")

    console.print(f"  [7]   Skip / Continue (configure later)\n")
    choices = ["1", "2", "3", "4", "5", "6", "7"]
    choice = Prompt.ask("\n  Choose a provider to add", choices=choices, default="7")

    if choice != "7":
        name, env_key, url = provider_options[choice]
        key = Prompt.ask(f"\n  Paste your {name} API key (input is hidden)", password=True)
        if key and key.strip():
            # Ensure .env file exists
            if not Path(_ENV_PATH).exists():
                Path(_ENV_PATH).write_text("# Lirox API Configuration\n")
            set_key(_ENV_PATH, env_key, key.strip())
            os.environ[env_key] = key.strip()
            console.print(f"\n  [success]✓ {name} key saved to .env[/success]")
            # Offer to add another
            another = Prompt.ask("\n  Add another key?", choices=["y", "n"], default="n")
            if another == "y":
                check_api_keys(force=True)
        else:
            console.print("\n  [warning]No key entered — skipped.[/warning]")
