import os
import sys
import argparse
import re
import json
from lirox.agent.core import LiroxAgent
from lirox.ui.display import (
    show_welcome, 
    show_status_card, 
    show_plan_table, 
    success_message, 
    error_panel, 
    info_panel, 
    thinking_panel,
    AgentSpinner,
    confirm_prompt,
    show_completion_art,
    CLR_LIROX, CLR_DIM, CLR_WARN
)
from lirox.utils.llm import is_task_request, available_providers
from lirox.utils.meta_parser import extract_meta
from lirox.config import APP_VERSION

def main():
    parser = argparse.ArgumentParser(description="Lirox Professional CLI Agent OS")
    parser.add_argument("--setup", action="store_true", help="Run initial agent setup")
    parser.add_argument("--task", type=str, help="Run a single autonomous task and exit")
    args = parser.parse_args()

    agent = LiroxAgent()
    show_welcome()

    # Initial Setup Check
    if not agent.profile.is_setup() or args.setup:
        run_setup(agent)

    # Single Task Mode
    if args.task:
        run_autonomous_task(agent, args.task)
        sys.exit(0)

    # Interactive Loop
    show_status_card(agent.profile.data, available_providers())
    
    while True:
        try:
            line = input(f"[{agent.profile.data.get('agent_name', 'Lirox')}] ✦ ").strip()
            if not line:
                continue

            if line.lower() in ("exit", "quit", "/exit"):
                info_panel("Shutting down Lirox Kernel. Goodbye.")
                break

            # Handle Commands
            if line.startswith("/"):
                handle_command(agent, line)
                continue

            # Process Message
            process_input(agent, line)

        except KeyboardInterrupt:
            print("\nInterrupt received. Use /exit to shut down safely.")
        except Exception as e:
            error_panel("KERNEL ERROR", str(e))

def process_input(agent, user_input):
    """v0.5.0 CLI-only Input Processor with LIROX_META signal parsing."""
    spinner = AgentSpinner("Processing...")
    spinner.start()
    
    try:
        # 1. Decide if this is a complex task
        is_task = is_task_request(user_input)
        
        if is_task:
            spinner.stop()
            run_autonomous_task(agent, user_input)
        else:
            # chat mode
            spinner.update_message("Synthesizing reasoning...")
            raw_response = agent.chat(user_input)
            
            # Clean up the output by extracting meta
            clean_text, meta = extract_meta(raw_response)
            
            spinner.stop()
            print(f"\n{clean_text}\n")
            
            # Mission intent signaling
            if meta.get("intent"):
                print(f"[{CLR_DIM}] SIGNED INTENT: {meta['intent']}[/]")
            
            if meta.get("risk_level") == "high":
                print(f"[{CLR_WARN}] [KERNEL WARNING] DEPLOYMENT RISK DETECTED: HIGH[/]")
            
    except Exception as e:
        spinner.stop()
        error_panel("AGENT ERROR", str(e))

def run_autonomous_task(agent, goal):
    """Professional task execution pipeline."""
    info_panel(f"Deployment Initialized: {goal}")
    
    # Reasoning Trace
    spinner = AgentSpinner("Architecting strategy...")
    spinner.start()
    thought = agent.reasoner.generate_thought_trace(goal)
    spinner.stop()
    thinking_panel(goal, thought)
    
    # Plan Construction
    spinner = AgentSpinner("Breaking down objectives...")
    spinner.start()
    plan = agent.planner.create_plan(goal, context=thought)
    spinner.stop()
    show_plan_table(plan)
    
    # Risk Assessment
    needs_confirm = any("terminal" in s.get("tools", []) for s in plan.get("steps", []))
    if needs_confirm:
        if not confirm_prompt("Mission includes [bold red]terminal commands[/]. Proceed with deployment?"):
            info_panel("Mission aborted by operator.")
            return

    # Execution
    info_panel("Engaging autonomous channels...")
    results, summary = agent.executor.execute_plan(plan)
    
    # Reflection & Learning
    reflection = agent.reasoner.generate_reasoning_summary(plan, results)
    
    # Reporting
    show_completion_art()
    success_message(summary)
    
    if reflection.get("reflection", {}).get("suggestion"):
        print(f"\n[{CLR_WARN}] AGENT REFLECTION: {reflection['reflection']['suggestion']}\n")

def handle_command(agent, command):
    cmd = command.lower().split()
    base = cmd[0]

    if base == "/profile":
        info_panel(f"AGENT IDENTITY PROTOCOL\n\n{agent.profile.summary()}")
    elif base == "/memory":
        stats = agent.memory.get_stats()
        text = f"Neural Connections: {stats['total_messages']}\nUser Signals: {stats['user_messages']}\nLast Update: {stats['newest']}"
        info_panel(f"MEMORY CORE STATUS\n\n{text}")
    elif base == "/clear":
        print(agent.memory.clear())
    elif base == "/trace":
        print(agent.executor.get_trace())
    elif base == "/reasoning":
        print(agent.reasoner.last_reasoning_text or "No reasoning history in current session.")
    elif base == "/models":
        avail = available_providers()
        text = "Available Providers:\n" + "\n".join([f"  • [bold green]{p}[/]" for p in avail])
        info_panel(f"LLM CHANNEL MAPPING\n\n{text}")
    elif base == "/add-api":
        run_api_setup()
    elif base == "/help":
        help_text = (
            "COMMAND REFERENCE\n\n"
            "  /profile    Show agent identity and profile\n"
            "  /memory     Show memory core statistics\n"
            "  /clear      Purge all conversation history\n"
            "  /trace      View low-level tool execution log\n"
            "  /reasoning  Review the last thought strategy\n"
            "  /models     List active LLM providers\n"
            "  /add-api    Configure API keys for providers\n"
            "  /exit       Safely terminate the Lirox kernel"
        )
        info_panel(help_text)
    else:
        print(f"Unknown command: {base}. Type /help for assistance.")

def run_setup(agent):
    info_panel("AGENT GENESIS PROTOCOL")
    agent_name = input("Designate Agent Name: ").strip() or "Lirox"
    user_name = input("Identity Operator: ").strip() or "Operator"
    niche = input("Primary Niche (e.g. Infosec, Dev, Research): ").strip() or "Generalist"
    
    agent.profile.update("agent_name", agent_name)
    agent.profile.update("user_name", user_name)
    agent.profile.update("niche", niche)
    success_message(f"Neural pathways initialized. Welcome, {user_name}. I am {agent_name} v{APP_VERSION} CLI.")

def run_api_setup():
    info_panel("API CHANNEL CONFIGURATION")
    print("Add keys to activate providers (empty to skip):")
    providers = ["gemini", "groq", "openai", "openrouter", "deepseek", "anthropic"]
    env_path = os.path.join(os.getcwd(), ".env")
    current_keys = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    current_keys[k] = v
    for p in providers:
        key = input(f"  {p.upper()} API KEY: ").strip()
        if key:
            env_var = f"{p.upper()}_API_KEY"
            current_keys[env_var] = key
    with open(env_path, "w") as f:
        for k, v in current_keys.items():
            f.write(f"{k}={v}\n")
    success_message("Protocol updated. Provider mapping reloaded.")

if __name__ == "__main__":
    main()
