"""
Lirox v0.3 — CLI Entry Point

Main interactive loop with all v0.3 commands:
- /plan, /execute-plan, /reasoning, /trace
- /tasks, /schedule
- /update — pull latest version from GitHub
- All v0.2 commands preserved
"""

import sys
import os
import subprocess
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from lirox.agent.core import LiroxAgent
from lirox.ui.display import (
    console, print_logo, boot_animation, show_status_card,
    show_status_bar, agent_panel, error_panel, reasoning_panel,
    trace_panel, Panel, ROUNDED
)
from lirox.ui.wizard import run_setup_wizard, check_api_keys

# Prompt toolkit styles
pt_style = PTStyle.from_dict({
    'prompt': '#7eb8f7 bold',
})


def print_help():
    help_text = """
    ── v0.3 Agent Commands ──────────────────────────

    /plan "goal"      → Show plan for a goal (don't execute)
    /execute-plan     → Execute the last generated plan
    /reasoning        → Show agent's reasoning for last action
    /trace            → Show full execution trace (debug)
    /tasks            → List all scheduled tasks
    /schedule "goal"  → Schedule task for later

    ── Profile & Settings ───────────────────────────

    /profile          → View your current agent profile
    /setup            → Re-run the full setup wizard
    /set-goal "..."   → Add a goal to your profile
    /set-name Name    → Rename your agent
    /set-tone tone    → Change agent tone (direct|casual|formal|friendly)
    /provider model   → Switch provider (openai|gemini|groq|openrouter|deepseek|auto)

    ── Memory & System ──────────────────────────────

    /memory           → View recent conversation memory
    /memory-search q  → Search memory for a keyword
    /clear            → Clear conversation memory (keeps profile)
    /status           → Show system status
    /add-api          → Open API key setup
    /update           → Pull latest version from GitHub + reinstall deps
    /exit             → Quit Lirox
    """
    agent_panel(help_text, "Commands")


def run_update():
    """Pull latest code from GitHub and reinstall requirements."""
    project_root = Path(__file__).resolve().parent.parent
    req_file = project_root / "requirements.txt"

    console.print("\n[info]🔄 Checking for updates...[/info]")

    # Step 1: git pull
    result = subprocess.run(
        ["git", "pull", "origin", "main"],
        cwd=str(project_root),
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        console.print(f"[warning]Git pull failed:\n{result.stderr.strip()}[/warning]")
        return

    output = result.stdout.strip()
    if "Already up to date" in output:
        console.print(Panel(
            "✓ Already up to date. No changes pulled.",
            border_style="success", box=ROUNDED
        ))
    else:
        console.print(Panel(
            f"✓ Update pulled successfully:\n\n{output}",
            border_style="success", box=ROUNDED, title=" Git Update "
        ))

    # Step 2: reinstall requirements
    if req_file.exists():
        console.print("[info]📦 Reinstalling dependencies...[/info]")
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
            capture_output=True,
            text=True
        )
        if pip_result.returncode == 0:
            console.print("[success]✓ Dependencies up to date.[/success]")
        else:
            console.print(f"[warning]pip install errors:\n{pip_result.stderr.strip()}[/warning]")
    else:
        console.print("[warning]requirements.txt not found — skipping dependency install.[/warning]")

    console.print("[info]\n💡 Restart Lirox to apply updates: python3 -m lirox.main[/info]\n")


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
            user_input = session.prompt("You › ", style=pt_style).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[info]Goodbye.[/info]")
            break

        if not user_input:
            continue

        # ─── Handle Commands ──────────────────────────────────────────────

        lowered = user_input.lower()

        if lowered == "/exit":
            console.print("\n[info]Goodbye.[/info]")
            break

        if lowered == "/help":
            print_help()
            continue

        if lowered == "/profile":
            agent_panel(agent.profile.summary(), "Profile")
            continue

        if lowered == "/setup":
            run_setup_wizard(agent.profile)
            continue

        if lowered == "/status":
            p = agent.profile.data
            show_status_card(
                agent_name=p.get("agent_name", "Lirox"),
                user_name=p.get("user_name", "User"),
                goals=p.get("goals", []),
                provider=agent.provider,
                memory_count=len(agent.memory.history) // 2
            )
            continue

        if lowered.startswith("/set-goal "):
            goal = user_input[10:].strip().strip("\"'")
            if goal:
                agent.profile.add_goal(goal)
                console.print(Panel(f"Goal added: {goal}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /set-goal \"Goal text\"[/warning]")
            continue

        if lowered.startswith("/set-name "):
            name = user_input[10:].strip()
            if name:
                agent.profile.update("agent_name", name)
                console.print(Panel(f"Agent renamed to: {name}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /set-name NewName[/warning]")
            continue

        if lowered.startswith("/set-tone "):
            tone = user_input[10:].strip().lower()
            if tone in ["direct", "casual", "formal", "friendly"]:
                agent.profile.update("tone", tone)
                console.print(Panel(f"Tone updated to: {tone}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /set-tone direct|casual|formal|friendly[/warning]")
            continue

        if lowered.startswith("/provider "):
            prov = user_input[10:].strip().lower()
            if prov:
                agent.set_provider(prov)
                console.print(Panel(f"Provider set to: {prov}", border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /provider openai|gemini|groq|openrouter|deepseek|auto[/warning]")
            continue

        if lowered == "/memory":
            agent_panel(agent.memory.get_context(), "Memory")
            continue

        if lowered.startswith("/memory-search "):
            query = user_input[15:].strip()
            if query:
                results = agent.memory.search_memory(query)
                if results:
                    lines = [f"Found {len(results)} result(s) for '{query}':\n"]
                    for msg in results:
                        role = "User" if msg["role"] == "user" else "Agent"
                        lines.append(f"  {role}: {msg['content'][:100]}")
                    agent_panel("\n".join(lines), "Memory Search")
                else:
                    agent_panel(f"No results found for '{query}'", "Memory Search")
            else:
                console.print("[warning]Usage: /memory-search keyword[/warning]")
            continue

        if lowered == "/clear":
            msg = agent.memory.clear()
            console.print(f"[success]{msg}[/success]")
            continue

        if lowered == "/add-api":
            check_api_keys()
            continue

        # ─── v0.3 Commands ────────────────────────────────────────────────

        if lowered.startswith("/plan "):
            goal = user_input[6:].strip().strip("\"'")
            if goal:
                try:
                    agent.show_plan(goal)
                    console.print("[info]  Plan saved. Use /execute-plan to run it.[/info]")
                except Exception as e:
                    error_panel(f"Planning failed: {e}")
            else:
                console.print("[warning]Usage: /plan \"your goal\"[/warning]")
            continue

        if lowered == "/execute-plan":
            try:
                result = agent.execute_last_plan()
                agent_label = agent.profile.data.get("agent_name", "Lirox")
                agent_panel(result, agent_label)
            except Exception as e:
                error_panel(f"Execution failed: {e}")
            continue

        if lowered == "/reasoning":
            reasoning = agent.get_last_reasoning()
            reasoning_panel(reasoning)
            continue

        if lowered == "/trace":
            trace = agent.get_last_trace()
            trace_panel(trace)
            continue

        if lowered == "/tasks":
            tasks = agent.list_scheduled_tasks()
            agent_panel(tasks, "Scheduled Tasks")
            continue

        if lowered.startswith("/schedule "):
            # Parse: /schedule "goal" [when]
            parts = user_input[10:].strip()
            goal = parts.strip("\"'")
            when = "in_5_minutes"  # Default

            # Check if timing is specified after the goal
            timing_options = [
                "in_5_minutes", "in_10_minutes", "in_30_minutes",
                "in_1_hour", "in_2_hours", "daily_9am", "daily_6pm"
            ]
            for opt in timing_options:
                if opt in parts.lower():
                    when = opt
                    goal = parts.lower().replace(opt, "").strip().strip("\"'")
                    break

            if goal:
                result = agent.schedule_task(goal, when)
                console.print(Panel(result, border_style="success", box=ROUNDED))
            else:
                console.print("[warning]Usage: /schedule \"goal\" [in_5_minutes|daily_9am|...][/warning]")
            continue

        if lowered == "/update":
            run_update()
            continue

        # Unknown command
        if user_input.startswith("/"):
            console.print(f"[warning]Unknown command: {user_input}. Type /help for a list of commands.[/warning]")
            continue

        # ─── Main Agent Call ──────────────────────────────────────────────
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
