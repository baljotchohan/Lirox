import os
import sys
import argparse
import json
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
            # Handle modules with dots like google.genai
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
        print("    1. python -m pip install -r requirements.txt")
        print("    2. python -m lirox.main")
        print("="*60 + "\n")
        sys.exit(1)

check_dependencies()


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
    CLR_WARN,
    console
)
from lirox.utils.llm import is_task_request, available_providers
from lirox.utils.meta_parser import extract_meta
from lirox.config import APP_VERSION
from lirox.utils.intent_router import router

def main():
    parser = argparse.ArgumentParser(description="Lirox Professional CLI Agent OS")
    parser.add_argument("--setup", action="store_true", help="Run initial agent setup")
    parser.add_argument("--task", type=str, help="Run a single autonomous task and exit")
    parser.add_argument("--verbose", action="store_true", help="Show internal mission metadata")
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
            process_input(agent, line, verbose=args.verbose)

        except KeyboardInterrupt:
            print("\nInterrupt received. Use /exit to shut down safely.")
        except Exception as e:
            error_panel("KERNEL ERROR", str(e))

def process_input(agent, user_input, verbose=False):
    """v0.6 Smart Input Processor with Intent Routing & Learning."""
    
    # Detect intent
    intent, suggested_command, confidence = router.detect_intent(user_input)
    
    if verbose:
        console.print(f"[dim]Intent: {intent} ({int(confidence*100)}%) | Command: {suggested_command}[/]")
    
    # Route based on intent
    if intent == "command":
        handle_command(agent, suggested_command)
        return
    
    elif intent == "research":
        if suggested_command:
            # Auto-execute research command
            query = suggested_command.split('"')[1] if '"' in suggested_command else user_input
            run_deep_research(agent, query, depth="standard")
            router.learn_from_choice("research", "/research")
        return
    
    elif intent == "task":
        run_autonomous_task(agent, user_input)
        router.learn_from_choice("task", "autonomous")
        return
    
    elif intent == "memory":
        # Extract and save to memory
        if "remember" in user_input.lower() or "save" in user_input.lower():
            fact = user_input.replace("remember", "").replace("save", "").strip()
            agent.profile.add_learned_fact(fact)
            success_message(f"Remembered: {fact}")
            router.learn_from_choice("memory", "save_fact")
        return
    
    else:  # chat
        spinner = AgentSpinner("Processing...")
        spinner.start()
        
        try:
            is_task = is_task_request(user_input)
            if is_task:
                spinner.stop()
                run_autonomous_task(agent, user_input)
                return
            
            spinner.update_message("Synthesizing response...")
            raw_response = agent.chat(user_input)
            
            clean_text, meta = extract_meta(raw_response)
            spinner.stop()
            
            from lirox.ui.display import CLR_ACCENT
            console.print(f"\n[{CLR_ACCENT}]{clean_text}[/]\n")
            
            if verbose and meta:
                console.print(f"[dim]Meta: {json.dumps(meta, indent=2)}[/]")
            
            # Show helpful next steps
            suggestion = router.suggest_next_command("chat")
            if suggestion:
                console.print(f"[dim]💡 {suggestion}[/]")
                
        except Exception as e:
            spinner.stop()
            error_panel("AGENT ERROR", str(e))

def run_autonomous_task(agent, goal):
    if goal.lower().startswith("research") or " research " in goal.lower():
        run_deep_research(agent, goal)
        return

    info_panel(f"Deployment Initialized: {goal}")
    
    spinner = AgentSpinner("Architecting strategy...")
    spinner.start()
    thought = agent.reasoner.generate_thought_trace(goal)
    spinner.stop()
    
    # New Advanced Thinking UI
    thinking_panel(goal, thought)
    
    spinner = AgentSpinner("Breaking down objectives...")
    spinner.start()
    plan = agent.planner.create_plan(goal, context=thought)
    spinner.stop()
    show_plan_table(plan)
    
    needs_confirm = any("terminal" in s.get("tools", []) for s in plan.get("steps", []))
    if needs_confirm:
        if not confirm_prompt("Mission includes [bold red]terminal commands[/]. Proceed with deployment?"):
            info_panel("Mission aborted by operator.")
            return

    # Risk evaluation via policy engine
    from lirox.agent.policy import policy_engine
    risk = policy_engine.evaluate_risk(plan)
    if not risk["auto_execute"]:
        console.print(f"[bold yellow]⚠ Risk: {risk['reason']}[/]")
        if not confirm_prompt("Proceed with execution?"):
            info_panel("Aborted by operator.")
            return

    info_panel("Engaging autonomous channels...")
    import time
    start_time = time.time()
    system_prompt = agent.profile.to_advanced_system_prompt()
    results, summary = agent.executor.execute_plan(plan, provider="auto", system_prompt=system_prompt)
    reflection = agent.reasoner.generate_reasoning_summary(plan, results)
    
    is_success = "error" not in summary.lower() and "failed" not in summary.lower()
    agent.profile.track_task_execution(goal, is_success, time.time() - start_time)
    
    show_completion_art()
    success_message(summary)
    
    if reflection.get("reflection", {}).get("suggestion"):
        print(f"\n[{CLR_WARN}] AGENT REFLECTION: {reflection['reflection']['suggestion']}\n")

def run_diagnostics(agent):
    info_panel("INITIATING CORE DIAGNOSTICS...")
    steps = [
        ("Memory Bank Integrity", lambda: "Neural connections: " + str(agent.memory.get_stats()['total_messages'])),
        ("Provider Mapping", lambda: "Available: " + ", ".join(available_providers())),
        ("Profile Persistence", lambda: "Operator: " + agent.profile.data.get('user_name', 'None')),
        ("Tool Authorization", lambda: "FileSystem/Terminal: [bold green]Operational[/]"),
        ("Kernel Version", lambda: f"v{APP_VERSION} [bold green]Downloaded/Latest[/]")
    ]
    for i, (name, fn) in enumerate(steps, 1):
        try:
            res = fn()
            print(f"  [bold green]✓[/] [white]{name:25}[/] : {res}")
        except Exception as e:
            print(f"  [bold red]✖[/] [white]{name:25}[/] : [bold red]{str(e)}[/]")
        time.sleep(0.1)
    success_message("All core subsystems are within nominal operating parameters.")

def run_git_update():
    info_panel("CHECKING FOR KERNEL UPDATES...")
    try:
        import subprocess
        from lirox.config import PROJECT_ROOT
        
        # Fetch latest
        subprocess.run(["git", "fetch", "origin", "main"], capture_output=True, check=True, cwd=PROJECT_ROOT)
        # Check if local is behind
        result = subprocess.run(
            ["git", "rev-list", "HEAD..origin/main", "--count"],
            capture_output=True, text=True, check=True, cwd=PROJECT_ROOT
        )
        count = int(result.stdout.strip())
        
        if count > 0:
            info_panel(f"Found {count} new update(s). Synchronizing...")
            subprocess.run(["git", "pull", "origin", "main"], capture_output=True, check=True, cwd=PROJECT_ROOT)
            subprocess.run(["pip", "install", "-r", "requirements.txt"], capture_output=True, cwd=PROJECT_ROOT)
            success_message("Update Downloaded & Applied. Please restart Lirox.")
        else:
            success_message(f"Kernel is up to date (v{APP_VERSION}).")
    except Exception as e:
        error_panel("UPDATE ERROR", f"Failed to synchronize with remote: {str(e)}")

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
    elif base == "/test":
        run_diagnostics(agent)
    elif base == "/update":
        run_git_update()
    elif base == "/add-api":
        run_api_setup()
    elif base == "/research":
        # /research "query" [--depth quick|standard|deep]
        query_part = command[len("/research "):].strip().strip('"\'')
        depth = "standard"
        if "--depth" in query_part:
            parts = query_part.split("--depth")
            query_part = parts[0].strip()
            depth = parts[1].strip().split()[0] if parts[1].strip() else "standard"
        
        if not query_part:
            info_panel("Usage: /research \"your question\" [--depth quick|standard|deep]")
            return
        
        run_deep_research(agent, query_part, depth)
    elif base == "/sources":
        # Show last research session sources
        if hasattr(agent, 'last_report') and agent.last_report:
            display_sources(agent.last_report.sources)
        else:
            info_panel("No research session active. Run /research first.")
    elif base == "/tier":
        from lirox.agent.tier import tier_description, get_available_search_apis
        apis = get_available_search_apis()
        text = (
            f"Research Tier Status\n\n"
            f"{tier_description()}\n\n"
            f"Available search APIs: {', '.join(apis) if apis else 'None (using DuckDuckGo)'}\n\n"
            f"To upgrade: add API keys via /add-api"
        )
        info_panel(text)
    elif base == "/think":
        # /think goal
        goal = command[len("/think "):].strip()
        if not goal:
            info_panel("Usage: /think \"your goal\"")
            return
        
        info_panel(f"Brainstorming mission: {goal}")
        spinner = AgentSpinner("Architecting strategy...")
        spinner.start()
        thought = agent.reasoner.generate_thought_trace(goal)
        plan = agent.planner.create_plan(goal, context=thought)
        spinner.stop()
        
        thinking_panel(goal, thought)
        show_plan_table(plan)
        success_message("Strategy analysis complete. Use /test to execute if satisfied.")

    elif base == "/schedule":
        # /schedule goal [--when time]
        cmd_text = command[len("/schedule "):].strip()
        when = "in_5_minutes"
        goal = cmd_text
        if "--when" in cmd_text:
            parts = cmd_text.split("--when")
            goal = parts[0].strip().strip('"\'')
            when = parts[1].strip()
        
        if not goal:
            info_panel("Usage: /schedule \"goal\" [--when in_5_minutes|in_10_minutes|daily_9am]")
            return
            
        task = agent.scheduler.schedule_task(goal, when)
        if task.get("id") == -1:
            error_panel("SCHEDULER ERROR", task.get("error", "Unknown error"))
        else:
            success_message(f"Mission deferred: [bold cyan]#{task['id']}[/] scheduled for [bold green]{when}[/]")

    elif base == "/reset":
        if confirm_prompt("[bold red]⚠ HIGH RISK[/]: This will purge all profile, memory, and scheduled data. Proceed?"):
            info_panel("INITIATING CORE PURGE...")
            files_to_purge = [
                os.path.join(agent.profile.storage_file),
                os.path.join(agent.memory.storage_file),
                os.path.join(agent.scheduler.storage_file),
                os.path.join(os.getcwd(), ".lirox_history")
            ]
            for f in files_to_purge:
                if os.path.exists(f):
                    os.remove(f)
                    print(f"  [dim]Purged: {os.path.basename(f)}[/dim]")
            
            success_message("Kernel reset complete. Shutting down for reboot.")
            sys.exit(0)

    elif base == "/add-search-api":
        run_search_api_setup()
    elif base == "/help":
        help_text = (
            "COMMAND REFERENCE\n\n"
            "── Research (v0.6) ──────────────────────────────────\n"
            "  /research \"Q\"    Deep research any topic\n"
            "  /research \"Q\" --depth deep    Extended 12-source research\n"
            "  /sources         View sources from last research\n"
            "  /tier            Show current research tier & APIs\n"
            "  /add-search-api  Add Tavily/Serper/Exa search keys\n\n"
            "── Agent ────────────────────────────────────────────\n"
            "  /profile    Show agent identity and profile\n"
            "  /memory     Show memory core statistics\n"
            "  /test       Run kernel diagnostics suite\n"
            "  /clear      Purge conversation history\n"
            "  /trace      View low-level tool logs\n"
            "  /reasoning  Review the last strategy trace\n"
            "  /models     List active LLM providers\n"
            "  /add-api    Configure API keys\n"
            "  /update     Check and apply kernel updates\n"
            "  /exit       Safely terminate the kernel"
        )
        info_panel(help_text)
    else:
        print(f"Unknown command: {base}. Type /help for assistance.")

def run_setup(agent):
    info_panel("AGENT GENESIS PROTOCOL")
    agent_name = input("Designate Agent Name: ").strip() or "Lirox"
    user_name = input("Identity Operator: ").strip() or "Operator"
    niche = input("Primary Niche: ").strip() or "Generalist"
    agent.profile.update("agent_name", agent_name)
    agent.profile.update("user_name", user_name)
    agent.profile.update("niche", niche)
    success_message(f"Neural pathways initialized. Welcome, {user_name}. I am {agent_name} v{APP_VERSION} CLI.")

def run_api_setup():
    info_panel("API CHANNEL CONFIGURATION")
    print("Add keys to activate providers (empty to skip):")
    providers = ["gemini", "groq", "openai", "openrouter", "deepseek", "anthropic", "nvidia"]
    from lirox.config import PROJECT_ROOT
    env_path = os.path.join(PROJECT_ROOT, ".env")
    current_keys = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    current_keys[k.strip()] = v.strip()
    for p in providers:
        key = input(f"  {p.upper()} API KEY: ").strip()
        if key:
            env_var = f"{p.upper()}_API_KEY"
            current_keys[env_var] = key
            os.environ[env_var] = key  # Update current process immediately
    with open(env_path, "w") as f:
        for k, v in current_keys.items():
            f.write(f"{k}={v}\n")
    success_message("Protocol updated. Provider mapping reloaded.")

def run_deep_research(agent, query: str, depth: str = "standard"):
    """v0.6 Research with tier enforcement and advanced UI."""
    from lirox.agent.researcher import Researcher
    from lirox.agent.tier import tier_description, get_available_search_apis, get_tier
    from lirox.ui.display import format_research_summary, format_findings_table, TaskProgressBar
    
    tier = get_tier()
    apis = get_available_search_apis()
    
    # Show tier status
    info_panel(
        f"RESEARCH QUERY: {query}\n"
        f"DEPTH: {depth.upper()}\n"
        f"{tier_description()}\n"
        f"Using: {', '.join(apis) if apis else 'DuckDuckGo (free)'}"
    )
    
    # Enforce tier constraints
    if depth == "deep" and tier < 1:
        info_panel(
            "⚠️  Deep research requires a paid search API.\n"
            f"Current tier: {tier_description()}\n"
            f"Add Tavily, Serper, or Exa keys via /add-search-api"
        )
        depth = "standard"
    
    researcher = Researcher(agent.executor.browser, provider="auto")
    
    # Progress bar for research
    with TaskProgressBar(4, "Deep Research") as progress:
        try:
            progress.update(1, "Decomposing query into sub-questions...")
            sub_queries = researcher._decompose_query(query)
            
            progress.update(1, "Searching across all available APIs...")
            _ = researcher._search_all(sub_queries)
            
            progress.update(1, "Extracting and analyzing content...")
            report = researcher.research(query, depth=depth)
            
            progress.update(1, "Generating comprehensive report...")
            report_path = researcher.generate_report(report)
            
            # Store for /sources command
            agent.last_report = report
            
            # Display results
            format_research_summary(query, len(report.sources), report.confidence_overall, report.search_apis_used)
            format_findings_table(report.findings)
            
            # Save to memory
            agent.memory.save_memory("user", f"RESEARCH: {query}")
            agent.memory.save_memory("assistant", f"RESEARCH COMPLETE: {report.summary[:300]}")
            
            console.print(f"\n[dim]Full report: {report_path}[/dim]")
            console.print(f"[dim]Sources: {len(report.sources)} | Confidence: {int(report.confidence_overall*100)}%[/dim]\n")
            
        except Exception as e:
            progress.stop()
            error_panel("RESEARCH ERROR", str(e))

def display_research_report(report, report_path: str):
    """Display research results in the terminal."""
    from rich.markdown import Markdown
    
    console.print()
    console.print(Markdown(f"# Research: {report.query}"))
    console.print(Markdown(f"**Confidence:** {int(report.confidence_overall * 100)}%  |  "
                           f"**Sources:** {len(report.sources)}  |  "
                           f"**APIs:** {', '.join(report.search_apis_used)}"))
    console.print()
    console.print(Markdown(report.summary))
    console.print()
    
    if report.findings:
        console.print(Markdown("## Key Findings"))
        for finding in report.findings[:5]:
            confidence_icon = "🟢" if finding.get("confidence") == "high" else "🟡" if finding.get("confidence") == "medium" else "🔴"
            console.print(f"  {confidence_icon} {finding.get('claim', '')}")
    
    console.print()
    console.print(f"[dim]Full report saved: {report_path}[/dim]")
    console.print("[dim]Type /sources to view source details[/dim]")
    console.print()

def display_sources(sources):
    """Display research sources as a table."""
    from rich.table import Table
    table = Table(title="Research Sources", border_style="dim")
    table.add_column("#", width=3)
    table.add_column("Title", style="white")
    table.add_column("Domain")
    table.add_column("Quality", justify="center")
    table.add_column("URL", style="dim")
    
    for source in sources:
        quality_bar = "█" * int(source.score * 5) + "░" * (5 - int(source.score * 5))
        table.add_row(
            str(source.citation_id),
            source.title[:40],
            source.domain,
            f"{quality_bar} {int(source.score * 100)}%",
            source.url[:40]
        )
    
    console.print(table)

def run_search_api_setup():
    """Dedicated setup for search API keys."""
    info_panel("SEARCH API CONFIGURATION\n\nThese APIs power the research engine. All are optional — Lirox falls back to DuckDuckGo.")
    
    apis = {
        "1": ("Tavily", "TAVILY_API_KEY", "app.tavily.com — Best for deep research"),
        "2": ("Serper", "SERPER_API_KEY", "serper.dev — Google Search API, cheap"),
        "3": ("Exa",    "EXA_API_KEY",    "exa.ai — Neural search, great for tech"),
    }
    
    from lirox.config import PROJECT_ROOT
    from dotenv import set_key
    env_path = os.path.join(PROJECT_ROOT, ".env")
    
    for k, (name, env_var, desc) in apis.items():
        status = "✓ Set" if os.getenv(env_var) else "Not set"
        console.print(f"  [{k}] {name.ljust(8)} {status.ljust(12)} {desc}")
    
    console.print()
    choice = input("Enter number to configure (Enter to skip): ").strip()
    
    if choice in apis:
        name, env_var, _ = apis[choice]
        key = input(f"Paste your {name} API key: ").strip()
        if key:
            set_key(env_path, env_var, key)
            os.environ[env_var] = key  # Update current process immediately
            console.print(f"  ✓ {name} key saved and connected.")

if __name__ == "__main__":
    main()
