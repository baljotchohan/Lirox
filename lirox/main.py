import sys
import os
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from lirox.agent.core import LiroxAgent
from lirox.ui.display import console, print_logo, boot_animation, show_status_card, show_status_bar, agent_panel, error_panel
from lirox.ui.wizard import run_setup_wizard, check_api_keys

# Prompt toolkit styles
pt_style = PTStyle.from_dict({
    'prompt': '#7eb8f7 bold',
})

def print_help():
    help_text = """
    /profile          → View your current agent profile
    /setup            → Re-run the full setup wizard
    /set-goal "..."   → Add a goal to your profile
    /set-name Name    → Rename your agent
    /set-tone tone    → Change agent tone (direct|casual|formal|friendly)
    /provider model   → Switch provider (openai|gemini|groq|openrouter|deepseek|auto)
    /memory           → View recent conversation memory
    /clear            → Clear conversation memory (keeps profile)
    /status           → Show system status
    /add-api          → Open API key setup
    /exit             → Quit Lirox
    """
    agent_panel(help_text, "Commands")

def main():
    # Load agent
    try:
        agent = LiroxAgent(provider="auto")
    except Exception as e:
        error_panel(f"Configuration error: {e}")
        return

    # First-run setup wizard
    if not agent.profile.is_setup():
        run_setup_wizard(agent.profile)
    
    # Boot sequence
    console.clear()
    print_logo()
    boot_animation()
    
    # Show status card
    p = agent.profile.data
    show_status_card(
        agent_name=p.get("agent_name", "Lirox"),
        user_name=p.get("user_name", "User"),
        goals=p.get("goals", []),
        provider=agent.provider,
        memory_count=len(agent.memory.history) // 2
    )

    # Input session
    session = PromptSession(history=FileHistory(".lirox_history"))

    while True:
        try:
            # Main prompt
            user_input = session.prompt("You › ", style=pt_style).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[info]Goodbye.[/info]")
            break

        if not user_input:
            continue

        # --- Handle Commands ---

        if user_input.lower() == "/exit":
            console.print("\n[info]Goodbye.[/info]")
            break

        if user_input.lower() == "/help":
            print_help()
            continue

        if user_input.lower() == "/profile":
            agent_panel(agent.profile.summary(), "Profile")
            continue

        if user_input.lower() == "/setup":
            run_setup_wizard(agent.profile)
            continue

        if user_input.lower() == "/status":
            show_status_card(
                agent_name=p.get("agent_name", "Lirox"),
                user_name=p.get("user_name", "User"),
                goals=p.get("goals", []),
                provider=agent.provider,
                memory_count=len(agent.memory.history) // 2
            )
            continue

        if user_input.lower().startswith("/set-goal "):
            goal = user_input[10:].strip().strip("\"'")
            if goal:
                agent.profile.add_goal(goal)
                console.print(Panel(f"Goal added: {goal}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /set-goal \"Goal text\"[/warning]")
            continue

        if user_input.lower().startswith("/set-name "):
            name = user_input[10:].strip()
            if name:
                agent.profile.update("agent_name", name)
                console.print(Panel(f"Agent renamed to: {name}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /set-name NewName[/warning]")
            continue

        if user_input.lower().startswith("/set-tone "):
            tone = user_input[10:].strip().lower()
            if tone in ["direct", "casual", "formal", "friendly"]:
                agent.profile.update("tone", tone)
                console.print(Panel(f"Tone updated to: {tone}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /set-tone direct|casual|formal|friendly[/warning]")
            continue

        if user_input.lower().startswith("/provider "):
            prov = user_input[10:].strip().lower()
            if prov:
                agent.set_provider(prov)
                console.print(Panel(f"Provider set to: {prov}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /provider openai|gemini|groq|openrouter|deepseek|auto[/warning]")
            continue

        if user_input.lower() == "/memory":
            agent_panel(agent.memory.get_context(), "Memory")
            continue

        if user_input.lower() == "/clear":
            agent.memory.clear()
            console.print("[success]Conversation memory cleared.[/success]")
            continue

        if user_input.lower() == "/add-api":
            check_api_keys()
            continue

        if user_input.startswith("/"):
            console.print(f"[warning]Unknown command: {user_input}. Type /help for a list of commands.[/warning]")
            continue

        # --- Main agent call ---
        try:
            response = agent.process_input(user_input)
            agent_label = agent.profile.data.get("agent_name", "Lirox")
            agent_panel(response, agent_label)
            
            # Show status bar after each turn
            show_status_bar(
                provider=agent.provider,
                memory_count=len(agent.memory.history) // 2,
                agent_name=agent_label,
                user_name=agent.profile.data.get("user_name", "User")
            )
        except Exception as e:
            error_panel(f"Error processing input: {e}")

if __name__ == "__main__":
    main()
