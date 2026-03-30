import os
from lirox.ui.display import console, Panel, ROUNDED
from rich.prompt import Prompt, IntPrompt
from dotenv import set_key

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
        "1": ("Direct", "No fluff. Get to the point fast."),
        "2": ("Friendly", "Warm, encouraging, supportive."),
        "3": ("Formal", "Professional tone at all times."),
        "4": ("Casual", "Relaxed and conversational.")
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

    # API Keys check
    check_api_keys()

    console.clear()
    console.print(Panel(
        f"✓ Profile saved\n\nAgent:  {agent_name}\nUser:   {user_name}\nNiche:  {niche}\nTone:   {tone_options[tone_choice][0]}\n\n{agent_name} is ready. Type anything to begin.",
        border_style="success", box=ROUNDED, title=" Setup Complete "
    ))

def check_api_keys():
    """Integrated API key setup."""
    providers = ["GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY"]
    existing = [p for p in providers if os.getenv(p)]
    
    if not existing:
        console.print("\n" + "─" * 40)
        console.print("  Add at least one LLM API key to continue")
        console.print("─" * 40 + "\n")
        
        provider_options = {
            "1": ("Gemini", "GEMINI_API_KEY", "aistudio.google.com"),
            "2": ("Groq", "GROQ_API_KEY", "console.groq.com"),
            "3": ("OpenAI", "OPENAI_API_KEY", "platform.openai.com"),
            "4": ("OpenRouter", "OPENROUTER_API_KEY", "openrouter.ai"),
            "5": ("DeepSeek", "DEEPSEEK_API_KEY", "platform.deepseek.com")
        }
        
        for k, (name, env_key, url) in provider_options.items():
            console.print(f"  [{k}] {name.ljust(12)} ({url})")
        
        console.print("  [6] Skip / Continue (configure later)\n")
        choice = Prompt.ask("\n  Choice", choices=["1", "2", "3", "4", "5", "6"], default="1")
        
        if choice != "6":
            name, env_key, url = provider_options[choice]
            key = Prompt.ask(f"\n  Paste your {name} API key")
            if key:
                # Update .env
                set_key(".env", env_key, key)
                os.environ[env_key] = key
                console.print(f"\n  [success]✓ {name} key saved to .env[/success]\n")
