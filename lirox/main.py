import os
import sys
import argparse
import time

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

try:
    import urllib3
    warnings.simplefilter('ignore', urllib3.exceptions.NotOpenSSLWarning)
except ImportError:
    pass

def check_dependencies():
    """Ensure all critical dependencies are present before starting."""
    import sys
    required = {
        "rich": "rich",
        "prompt_toolkit": "prompt-toolkit",
        "psutil": "psutil",
        "google.genai": "google-genai",
        "dotenv": "python-dotenv",
        "bs4": "beautifulsoup4",
        "lxml": "lxml"
    }
    missing = []
    for mod, pkg in required.items():
        try:
            __import__(mod.split('.')[0])
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print("\n" + "="*60)
        print(" [!] KERNEL INITIALIZATION FAILURE: MISSING DEPENDENCIES")
        print("="*60)
        print(f" The following packages are required but not found:")
        for pkg in missing:
            print(f"    • {pkg}")
        print("\n TO FIX, RUN BOTH COMMANDS IN YOUR TERMINAL:")
        print("    1. pip install -e .          (installs lirox CLI)")
        print("    2. lirox                     (or: python -m lirox)")
        print("="*60 + "\n")
        sys.exit(1)

check_dependencies()

from lirox.agent.core import LiroxAgent
from lirox.ui.display import (
    show_welcome, 
    show_status_card, 
    error_panel, 
    info_panel,
    console
)
from lirox.utils.llm import available_providers
from lirox.config import APP_VERSION

def main():
    parser = argparse.ArgumentParser(description="Lirox Professional CLI Agent OS")
    parser.add_argument("--setup", action="store_true", help="Run initial agent setup")
    parser.add_argument("--verbose", action="store_true", help="Show internal mission metadata")
    args = parser.parse_args()

    from lirox.utils.startup_validator import StartupValidator
    ok, warnings = StartupValidator.validate_all()
    if not ok:
        for w in warnings:
            console.print(f"  [WARNING] {w}")
    elif warnings:
        for w in warnings:
            console.print(f"  [!] {w}")

    agent = LiroxAgent()
    show_welcome()

    if not agent.profile.is_setup() or args.setup:
        run_setup(agent)

    show_status_card(agent.profile.data, available_providers(), token_status=None)
    
    last_interrupt_time = 0
    while True:
        try:
            line = input(f"[{agent.profile.data.get('agent_name', 'Lirox')}] ✦ ").strip()
            if not line:
                continue

            if line.lower() in ("exit", "quit", "/exit"):
                info_panel("Shutting down Lirox Kernel. Goodbye.")
                break

            if line.startswith("/"):
                handle_command(agent, line)
                continue

            process_input(agent, line, verbose=args.verbose)

        except KeyboardInterrupt:
            current_time = time.time()
            if current_time - last_interrupt_time < 2.0:
                print("\n[!] Force quitting Lirox...")
                sys.exit(0)
            else:
                print("\n[!] Interrupt received. Press Ctrl+C again within 2 seconds to force quit, or type /exit.")
                last_interrupt_time = current_time
        except Exception as e:
            error_panel("KERNEL ERROR", str(e))

def process_input(agent, user_input, verbose=False):
    """v1.0 Skill-based input processor."""
    from lirox.skills import registry
    from lirox.utils.meta_parser import extract_meta
    from lirox.ui.display import console, CLR_ACCENT, CLR_DIM, error_panel
    import re
    
    try:
        # Route to best skill
        skill = registry.route(user_input)
        
        if skill is None:
            # Absolute fallback to chat
            skill = registry.get("chat")
        
        if verbose:
            console.print(f"[{CLR_DIM}]Skill: {skill.name} | Risk: {skill.risk_level.value}[/]")
        
        # Build context from agent state
        context = {
            "system_prompt": agent.profile.to_advanced_system_prompt(),
            "memory": agent.memory.get_relevant_context(user_input),
        }
        
        # HIGH risk skills need confirmation
        if skill.risk_level.value == "high":
            from lirox.ui.display import confirm_prompt
            if not confirm_prompt(f"Skill [{skill.name}] requires elevated permissions. Proceed?"):
                console.print(f"[{CLR_DIM}]Cancelled.[/]\n")
                return
        
        # Execute
        result = skill.execute(user_input, context)
        
        # Clean and display
        output = result.output
        output, _ = extract_meta(output)
        output = re.sub(r'\*\*(.+?)\*\*', r'\1', output)  # Strip bold
        output = re.sub(r'^\[.*?\]\s*✦?\s*', '', output)   # Strip agent prefix
        
        console.print(f"\n[{CLR_ACCENT}]{output.strip()}[/]\n")
        
        # Show sources if available
        if result.sources:
            console.print(f"[{CLR_DIM}]Sources: {len(result.sources)} | Confidence: {result.confidence:.0%}[/]")
        
        # Save to memory
        agent.memory.save_memory("user", user_input)
        agent.memory.save_memory("assistant", result.output[:500])
        
        # Learning hook
        if hasattr(agent, 'learning'):
            agent.learning.on_interaction(user_input, result.output)
        
    except Exception as e:
        error_panel("EXECUTION ERROR", str(e))

def handle_command(agent, command):
    cmd = command.lower().split()
    base = cmd[0]
    
    if base == "/help":
        _show_help(agent)
    
    elif base == "/skills":
        # Show all skills with status
        from lirox.skills import registry
        from lirox.ui.display import info_panel
        info_panel(f"SKILL POOL\n\n{registry.summary()}")
    
    elif base in ("/enable", "/disable"):
        # /enable bash  or  /disable bash
        from lirox.skills import registry
        if len(cmd) < 2:
            print(f"Usage: {base} <skill_name>")
            return
        skill_name = cmd[1]
        if base == "/enable":
            registry.enable(skill_name)
            print(f"  Skill '{skill_name}' enabled.")
        else:
            registry.disable(skill_name)
            print(f"  Skill '{skill_name}' disabled.")
    
    elif base == "/research":
        query = command[len("/research "):].strip().strip("\"'")
        if not query:
            from lirox.ui.display import info_panel
            info_panel("Usage: /research \"your question\"")
            return
        from lirox.skills import registry
        skill = registry.get("research")
        if skill:
            result = skill.execute(query)
            from lirox.ui.display import console, CLR_ACCENT
            console.print(f"\n[{CLR_ACCENT}]{result.output}[/]\n")
        else:
            from lirox.ui.display import info_panel
            info_panel("Research skill not available.")
    
    elif base in ("/web", "/fetch", "/scrape"):
        url = command.split(None, 1)[1].strip().strip("\"'") if len(cmd) > 1 else ""
        if not url:
            from lirox.ui.display import info_panel
            info_panel("Usage: /web <url>")
            return
        from lirox.skills import registry
        skill = registry.get("web_fetch")
        if skill:
            result = skill.execute(url)
            from lirox.ui.display import console, CLR_ACCENT
            console.print(f"\n[{CLR_ACCENT}]{result.output[:3000]}[/]\n")
    
    elif base == "/profile":
        from lirox.ui.display import info_panel
        stats = agent.memory.get_stats()
        learning = ""
        try:
            learning = agent.learning.get_user_profile_summary()
        except Exception:
            pass
        text = (
            f"AGENT IDENTITY\n\n{agent.profile.summary()}\n\n"
            f"MEMORY: {stats['total_messages']} messages\n\n"
        )
        if learning:
            text += f"LEARNING\n{learning}\n"
        info_panel(text)
    
    elif base == "/models":
        from lirox.utils.llm import available_providers
        from lirox.ui.display import info_panel
        avail = available_providers()
        text = "Active Providers:\n" + "\n".join(f"  {p}" for p in avail)
        info_panel(f"LLM PROVIDERS\n\n{text}")
    
    elif base == "/test":
        run_diagnostics(agent)
    
    elif base == "/update":
        run_git_update()
    
    elif base == "/reset":
        from lirox.ui.display import confirm_prompt, info_panel, success_message, console
        if confirm_prompt("This will purge ALL data. Are you sure?"):
            info_panel("INITIATING CORE PURGE...")
            files_to_purge = [
                os.path.join(agent.profile.storage_file),
                os.path.join(agent.memory.storage_file),
                os.path.join(os.getcwd(), ".lirox_history")
            ]
            from lirox.config import DATA_DIR
            learn_path = os.path.join(DATA_DIR, "learning_engine.json")
            files_to_purge.append(learn_path)

            for f in files_to_purge:
                if f and os.path.exists(f):
                    os.remove(f)
                    console.print(f"  [dim]Purged: {os.path.basename(f)}[/dim]")

            success_message("Kernel reset complete. Shutting down for reboot.")
            sys.exit(0)
    
    elif base in ("exit", "quit", "/exit"):
        from lirox.ui.display import info_panel
        info_panel("Shutting down. Goodbye.")
        import sys
        sys.exit(0)
    
    else:
        print(f"Unknown command: {base}. Type /help for commands.")

def _show_help(agent):
    from rich.table import Table
    from rich.panel import Panel
    from rich.box import ROUNDED
    from lirox.config import APP_VERSION
    from lirox.ui.display import console, CLR_LIROX

    table = Table(show_header=True, header_style="bold #FFC107", border_style="dim", padding=(0, 1))
    table.add_column("Command", style="bold white", no_wrap=True)
    table.add_column("Description", style="dim white")

    rows = [
        ("/help", "Show this help"),
        ("/skills", "List all skills"),
        ("/enable <skill>", "Enable a skill"),
        ("/disable <skill>", "Disable a skill"),
        ("/research <q>", "Research a topic"),
        ("/web <url>", "Fetch a URL"),
        ("/profile", "Agent & user info"),
        ("/models", "List LLMs"),
        ("/test", "Run diagnostics"),
        ("/update", "Update repo"),
        ("/reset", "Reset all memory"),
    ]
    for cmd, desc in rows:
        table.add_row(cmd, desc)

    console.print(Panel(
        table,
        title=f"[{CLR_LIROX}] LIROX v{APP_VERSION} — COMMAND REFERENCE [/]",
        border_style=CLR_LIROX,
        box=ROUNDED,
        padding=(1, 2)
    ))

def run_diagnostics(agent):
    from lirox.ui.display import info_panel, console, success_message
    from lirox.config import APP_VERSION
    info_panel("INITIATING CORE DIAGNOSTICS...")
    steps = [
        ("Memory Bank Integrity", lambda: "Neural connections: " + str(agent.memory.get_stats()['total_messages'])),
        ("Provider Mapping", lambda: "Available: " + ", ".join(available_providers())),
        ("Profile Persistence", lambda: "Operator: " + agent.profile.data.get('user_name', 'None')),
        ("Kernel Version", lambda: f"v{APP_VERSION} [bold green]Downloaded/Latest[/]"),
    ]
    import time
    for i, (name, fn) in enumerate(steps, 1):
        try:
            res = fn()
            console.print(f"  [bold green]✓[/] [white]{name:25}[/] : {res}")
        except Exception as e:
            console.print(f"  [bold red]✖[/] [white]{name:25}[/] : [bold red]{str(e)}[/]")
        time.sleep(0.1)
    success_message("All core subsystems are within nominal operating parameters.")

def run_git_update():
    from lirox.ui.display import info_panel, success_message, error_panel, console
    info_panel("CHECKING FOR KERNEL UPDATES...")
    try:
        import subprocess
        import sys
        from lirox.config import PROJECT_ROOT
        
        def stream_command(cmd, cwd=None):
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cwd)
            for line in process.stdout:
                console.print(f"  [dim]» {line.strip()}[/dim]")
            process.wait()
            return process.returncode

        res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT)
        branch = res.stdout.strip() or "main"
        
        info_panel(f"Synchronizing [bold cyan]{branch}[/] branch. Stashing local edits...")
        subprocess.run(["git", "stash"], capture_output=True, cwd=PROJECT_ROOT)
        
        subprocess.run(["git", "fetch", "origin", branch], capture_output=True, cwd=PROJECT_ROOT)
        result = subprocess.run(["git", "rev-list", f"HEAD..origin/{branch}", "--count"], capture_output=True, text=True, cwd=PROJECT_ROOT)
        count = int(result.stdout.strip() or "0")
        
        if count > 0:
            info_panel(f"Found {count} update(s). Synchronizing kernel...")
            if stream_command(["git", "pull", "origin", branch], cwd=PROJECT_ROOT) != 0:
                raise Exception("Git pull failed.")
            info_panel("Synchronizing dependencies...")
            stream_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=PROJECT_ROOT)
            success_message("Kernel updated. Restart Lirox to apply changes.")
        else:
            subprocess.run(["git", "stash", "pop"], capture_output=True, cwd=PROJECT_ROOT)
            success_message("Kernel is up to date.")
            
    except Exception as e:
        error_panel("UPDATE ERROR", str(e))

def run_setup(agent):
    from lirox.ui.wizard import run_setup_wizard
    from lirox.ui.display import console
    try:
        run_setup_wizard(agent.profile)
    except KeyboardInterrupt:
        console.print("\n  [dim]Setup interrupted. Using defaults.[/dim]")
        if not agent.profile.data.get("agent_name"):
            agent.profile.update("agent_name", "Lirox")
        if not agent.profile.data.get("user_name"):
            agent.profile.update("user_name", "Operator")
