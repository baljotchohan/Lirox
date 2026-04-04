import os
from pathlib import Path
from rich.panel import Panel
from rich.box import ROUNDED
from lirox.ui.display import console
from rich.prompt import Prompt
from dotenv import set_key

_PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = str(_PROJECT_ROOT_DIR / ".env")

def run_setup_wizard(profile):
    console.clear()
    console.print(Panel(
        "Welcome to Lirox v2.0. Let's set you up.",
        border_style="bold #FFC107", box=ROUNDED, width=60
    ))
    
    agent_options = {
        "1": "Lirox",
        "2": "Atlas",
        "3": "Nova",
        "4": "Rex"
    }
    console.print("\n  Select your agent name:")
    for k, v in agent_options.items():
        console.print(f"  [{k}] {v}")
    
    agent_choice = Prompt.ask("\n  Choose (1-4)", choices=["1", "2", "3", "4"], default="1")
    agent_name = agent_options[agent_choice]
    profile.update("agent_name", agent_name)
    
    user_name = Prompt.ask("\n  What's your name?")
    profile.update("user_name", user_name)
    
    niche_options = {
        "1": "Developer",
        "2": "Founder",
        "3": "Content Creator",
        "4": "Researcher",
        "5": "Student",
        "6": "Data Scientist",
        "7": "Designer",
        "8": "Marketer",
        "9": "Writer",
        "10": "Other"
    }
    console.print("\n  Select your primary niche:")
    for k, v in niche_options.items():
        console.print(f"  [{k}] {v}")
    
    niche_choice = Prompt.ask("\n  Choose (1-10)", choices=[str(i) for i in range(1, 11)], default="1")
    niche = niche_options[niche_choice]
    profile.update("niche", niche)
    
    check_api_keys(force=True)
    
    console.clear()
    console.print(Panel(
        f"✓ Profile saved\n\n"
        f"Agent:  {agent_name}\n"
        f"User:   {user_name}\n"
        f"Niche:  {niche}\n\n"
        f"{agent_name} is ready.",
        border_style="green", box=ROUNDED, title=" Setup Complete "
    ))

    choice = Prompt.ask("\n  What's next?", choices=["1", "2"], default="1")
    if choice == "2":
        from lirox.skills import registry
        console.print(f"\n{registry.summary()}\n")

def check_api_keys(force=False):
    provider_options = {
        "1": ("Gemini", "GEMINI_API_KEY", "aistudio.google.com"),
        "2": ("Groq", "GROQ_API_KEY", "console.groq.com"),
        "3": ("OpenRouter", "OPENROUTER_API_KEY", "openrouter.ai"),
        "4": ("OpenAI", "OPENAI_API_KEY", "platform.openai.com"),
        "5": ("Anthropic", "ANTHROPIC_API_KEY", "console.anthropic.com")
    }
    
    existing = [name for _, (name, env_key, _) in provider_options.items() if os.getenv(env_key)]
    if not force and existing:
        return

    console.print("\n  Let's connect an LLM. Groq or Gemini are recommended (free).")
    for k, (name, env_key, url) in provider_options.items():
        status = " ✓" if os.getenv(env_key) else "  "
        console.print(f"  [{k}]{status} {name.ljust(12)} {url}")
        
    console.print("  [6]   Skip")
    choice = Prompt.ask("\n  Choose a provider to add", choices=["1", "2", "3", "4", "5", "6"], default="6")
    if choice != "6":
        name, env_key, url = provider_options[choice]
        key = Prompt.ask(f"\n  Paste {name} API key", password=True)
        if key:
            if not Path(_ENV_PATH).exists():
                Path(_ENV_PATH).write_text("# Lirox API Configuration\n")
            set_key(_ENV_PATH, env_key, key.strip())
            os.environ[env_key] = key.strip()
            console.print(f"\n  [bold green]✓ Key saved[/bold green]")
            if Prompt.ask("\n  Add another?", choices=["y", "n"], default="n") == "y":
                check_api_keys(force=True)
