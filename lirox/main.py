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
        print("    1. pip install -e .          (installs lirox CLI)")
        print("    2. lirox                     (or: python -m lirox)")
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
from lirox.agent.unified_executor import UnifiedExecutor
from lirox.utils.response_formatter import format_for_display

def main():
    parser = argparse.ArgumentParser(description="Lirox Professional CLI Agent OS")
    parser.add_argument("--setup", action="store_true", help="Run initial agent setup")
    parser.add_argument("--task", type=str, help="Run a single autonomous task and exit")
    parser.add_argument("--verbose", action="store_true", help="Show internal mission metadata")
    args = parser.parse_args()

    from lirox.utils.startup_validator import StartupValidator
    ok, warnings = StartupValidator.validate_all()
    if not ok:
        # Warn but don't exit — new users need to reach onboarding first
        for w in warnings:
            print(f"  [WARNING] {w}")
    elif warnings:
        for w in warnings:
            print(f"  [!] {w}")

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
    tokens = agent.executor.get_browser_token_status()
    show_status_card(agent.profile.data, available_providers(), token_status=tokens)
    
    last_interrupt_time = 0
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
            current_time = time.time()
            if current_time - last_interrupt_time < 2.0:
                print("\n[!] Force quitting Lirox...")
                sys.exit(0)
            else:
                print("\n[!] Interrupt received. Press Ctrl+C again within 2 seconds to force quit, or type /exit.")
                last_interrupt_time = current_time
        except Exception as e:
            error_panel("KERNEL ERROR", str(e))

# ─── Singleton cache for UnifiedExecutor (FIX 1.3) ──────────────────────────
_executor_cache: dict = {}


def process_input(agent, user_input, verbose=False):
    """v0.8.5 Smart Input Processor with Unified Router."""
    global _executor_cache

    cache_key = f"{id(agent)}_auto"
    if cache_key not in _executor_cache:
        from lirox.agent.unified_executor import UnifiedExecutor
        _executor_cache[cache_key] = UnifiedExecutor(provider="auto", verbose=verbose)

    unified = _executor_cache[cache_key]

    try:
        # Execute using optimal mode
        result = unified.execute(user_input, system_prompt=agent.profile.to_advanced_system_prompt())

        # Format and display
        from lirox.utils.response_formatter import format_for_display
        formatted_response = format_for_display(result)

        from lirox.ui.display import CLR_ACCENT
        console.print(f"\n[{CLR_ACCENT}]{formatted_response}[/]\n")

        # Save to memory
        agent.memory.save_memory("user", user_input)
        agent.memory.save_memory("assistant", result.get("answer", ""))

    except Exception as e:
        error_panel("EXECUTION ERROR", str(e))


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
    
    # [FIX #8] Mandatory confirmation loop for elevated risks
    if not risk["auto_execute"] or risk.get("risk_level") in ["medium", "high"]:
        console.print(f"[bold yellow]⚠ Risk Level ({risk.get('risk_level', 'unknown')}): {risk['reason']}[/]")
        if not confirm_prompt("Proceed with autonomous execution?"):
            info_panel("Aborted by operator.")
            return

    info_panel("Engaging autonomous channels...")
    import time
    start_time = time.time()
    system_prompt = agent.profile.to_advanced_system_prompt()
    results, summary = agent.executor.execute_plan(plan, provider="auto", system_prompt=system_prompt)
    reflection = agent.reasoner.generate_reasoning_summary(plan, results)
    
    # Clean any JSON metadata from the summary before display
    summary, _ = extract_meta(summary)
    
    is_success = "error" not in summary.lower() and "failed" not in summary.lower()
    agent.profile.track_task_execution(goal, is_success, time.time() - start_time)
    
    show_completion_art()
    success_message(summary)
    
    if reflection.get("reflection", {}).get("suggestion"):
        suggestion = reflection['reflection']['suggestion']
        # Clean: remove redundant emoji prefixes
        suggestion = suggestion.replace("✅ ", "").replace("⚠️ ", "")
        console.print(f"\n[{CLR_WARN}]💡 {suggestion}[/]\n")

def _check_browser_status():
    """v0.7: Helper for diagnostics — check browser subsystem."""
    try:
        from lirox.tools.browser_tool import get_browser_status
        status = get_browser_status()
        if status['binary_available']:
            return f"[bold green]Lightpanda Available[/] ({status.get('binary_path', 'N/A')})"
        else:
            return "[bold yellow]Binary Not Found[/] (optional — install Lightpanda for headless browser)"
    except ImportError:
        return "[dim]Not installed[/]"
    except Exception as e:
        return f"[bold red]Error: {str(e)}[/]"

def run_diagnostics(agent):
    info_panel("INITIATING CORE DIAGNOSTICS...")
    steps = [
        ("Memory Bank Integrity", lambda: "Neural connections: " + str(agent.memory.get_stats()['total_messages'])),
        ("Provider Mapping", lambda: "Available: " + ", ".join(available_providers())),
        ("Profile Persistence", lambda: "Operator: " + agent.profile.data.get('user_name', 'None')),
        ("Tool Authorization", lambda: "FileSystem/Terminal: [bold green]Operational[/]"),
        ("Kernel Version", lambda: f"v{APP_VERSION} [bold green]Downloaded/Latest[/]"),
        ("Headless Browser", lambda: _check_browser_status()),
    ]
    for i, (name, fn) in enumerate(steps, 1):
        try:
            res = fn()
            console.print(f"  [bold green]✓[/] [white]{name:25}[/] : {res}")
        except Exception as e:
            console.print(f"  [bold red]✖[/] [white]{name:25}[/] : [bold red]{str(e)}[/]")
        time.sleep(0.1)
    success_message("All core subsystems are within nominal operating parameters.")

def run_git_update():
    """v0.6 Hardened Update Protocol: Stash, Pull, Sync requirements, and Stream output."""
    info_panel("CHECKING FOR KERNEL UPDATES...")
    try:
        import subprocess
        import sys
        from lirox.config import PROJECT_ROOT
        
        def stream_command(cmd, cwd=None):
            """Run a command and stream output to the console in real-time."""
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, shell=False, cwd=cwd
            )
            for line in process.stdout:
                console.print(f"  [dim]» {line.strip()}[/dim]")
            process.wait()
            return process.returncode

        # 1. Detect current branch
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
            capture_output=True, text=True, check=True, cwd=PROJECT_ROOT
        )
        branch = res.stdout.strip() or "main"
        
        # 2. Stash local changes (safety first)
        info_panel(f"Synchronizing [bold cyan]{branch}[/] branch. Stashing local edits...")
        subprocess.run(["git", "stash"], capture_output=True, cwd=PROJECT_ROOT)
        
        # 3. Fetch and Check
        subprocess.run(["git", "fetch", "origin", branch], capture_output=True, check=True, cwd=PROJECT_ROOT)
        result = subprocess.run(
            ["git", "rev-list", f"HEAD..origin/{branch}", "--count"],
            capture_output=True, text=True, check=True, cwd=PROJECT_ROOT
        )
        count = int(result.stdout.strip() or "0")
        
        if count > 0:
            info_panel(f"Found {count} update(s). Synchronizing kernel...")
            
            # Pull with streaming feedback
            if stream_command(["git", "pull", "origin", branch], cwd=PROJECT_ROOT) != 0:
                raise Exception("Git pull failed.")
            
            # Sync requirements using current interpreter
            info_panel("Synchronizing dependencies...")
            if stream_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=PROJECT_ROOT) != 0:
                success_message("Kernel updated, but dependency sync encountered a warning.")
            else:
                success_message("Kernel synchronization complete.")
            
            info_panel("NOTE: Please restart Lirox to apply architectural changes.")
        else:
            # Pop stash if no updates were found (optional, but polite)
            subprocess.run(["git", "stash", "pop"], capture_output=True, cwd=PROJECT_ROOT)
            success_message(f"Kernel is up to date (v{APP_VERSION}).")
            
    except Exception as e:
        error_panel("UPDATE ERROR", f"Kernel synchronization failed: {str(e)}")

def handle_command(agent, command):
    cmd = command.lower().split()
    base = cmd[0]

    if base == "/profile":
        from lirox.agent.learning_engine import LearningEngine
        stats = agent.learning.get_stats_display() if hasattr(agent, 'learning') else {}
        learn_text = ""
        if stats:
            top_i = ", ".join(f"{i}({c}x)" for i, c in stats.get("top_intents", [])[:3]) or "none"
            top_t = ", ".join(t for t, _ in stats.get("top_topics", [])[:5]) or "none"
            sat = stats.get("satisfaction_score", 1.0)
            learn_text = (
                f"\n\nLEARNING ENGINE\n"
                f"  Sessions   : {stats.get('total_sessions', 0)}\n"
                f"  Interactions: {stats.get('total_interactions', 0)}\n"
                f"  Top intents: {top_i}\n"
                f"  Hot topics : {top_t}\n"
                f"  Satisfaction: {sat:.0%}\n"
                f"  Peak hour  : {stats.get('most_active_hour', 'N/A')}:00"
            )
        info_panel(f"AGENT IDENTITY PROTOCOL\n\n{agent.profile.summary()}{learn_text}")
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
    elif base == "/smart":
        # /smart <query> — Use intelligent routing
        query = command[len("/smart "):].strip()
        if not query:
            info_panel("Usage: /smart \"your query\"\nAutomatically selects CHAT/RESEARCH/BROWSER/HYBRID mode")
            return
        
        from lirox.agent.unified_executor import UnifiedExecutor
        from lirox.utils.response_formatter import format_for_display
        
        unified = UnifiedExecutor(provider="auto", verbose=False)
        result = unified.execute(query, system_prompt=agent.profile.to_advanced_system_prompt())
        
        formatted = format_for_display(result)
        console.print(f"\n{formatted}\n")
        
        # Show routing decision
        stats = unified.get_routing_stats()
        info_panel(f"Mode: {result['mode']} | Confidence: {result.get('routing_confidence', 0):.0%}")

    elif base == "/router-stats":
        # Show routing statistics
        from lirox.agent.unified_executor import UnifiedExecutor
        unified = UnifiedExecutor()
        stats = unified.get_routing_stats()
        info_panel(
            f"ROUTING STATISTICS\n\n"
            f"Total Queries: {stats.get('total_queries', 0)}\n"
            f"Mode Distribution: {json.dumps(stats.get('mode_distribution', {}), indent=2)}\n"
            f"Avg Confidence: {stats.get('average_confidence', 0):.0%}\n"
            f"Most Common: {stats.get('most_common_mode', 'N/A')}"
        )
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
    
    elif base == "/run-task":
        # /run-task ID
        try:
            task_id = int(cmd[1])
            task = next((t for t in agent.scheduler.tasks if t["id"] == task_id), None)
            if not task:
                error_panel("SCHEDULER ERROR", f"Task #{task_id} not found.")
            else:
                info_panel(f"Force-executing Mission #{task_id}: {task['goal']}")
                agent.scheduler._execute_task(task_id)
                success_message(f"Task #{task_id} execution attempt complete.")
        except (IndexError, ValueError):
            info_panel("Usage: /run-task <ID>")

    elif base == "/reset":
        if confirm_prompt("[bold red]⚠ HIGH RISK[/]: This will purge all profile, memory, and scheduled data. Proceed?"):
            info_panel("INITIATING CORE PURGE...")
            files_to_purge = [
                os.path.join(agent.profile.storage_file),
                os.path.join(agent.memory.storage_file),
                os.path.join(agent.scheduler.storage_file),
                os.path.join(os.getcwd(), ".lirox_history")
            ]
            # Also purge learning engine
            from lirox.config import DATA_DIR
            learn_path = os.path.join(DATA_DIR, "learning_engine.json")
            files_to_purge.append(learn_path)

            for f in files_to_purge:
                if f and os.path.exists(f):
                    os.remove(f)
                    console.print(f"  [dim]Purged: {os.path.basename(f)}[/dim]")

            success_message("Kernel reset complete. Shutting down for reboot.")
            sys.exit(0)

    elif base == "/add-search-api":
        run_search_api_setup()
    elif base in ("/web", "/fetch", "/scrape", "/browser"):
        # Phase 9: /web is the unified alias; /fetch, /scrape, /browser still work
        if base == "/browser" and len(cmd) == 1:
            # Show browser status
            try:
                from lirox.tools.browser_tool import get_browser_status
                status = get_browser_status()
                binary_status = "[bold green]✓ Available[/]" if status['binary_available'] else "[bold red]✗ Not Found[/]"
                running = "[bold green]✓ Running[/]" if status.get('browser_running') else "[dim]Idle[/]"
                text = (
                    f"HEADLESS BROWSER SUBSYSTEM (v0.8.5)\n\n"
                    f"  Binary:    {binary_status}\n"
                    f"  Path:      {status.get('binary_path', 'N/A')}\n"
                    f"  Status:    {running}\n"
                    f"  Sessions:  {status.get('active_sessions', 0)}/{status.get('max_instances', 5)} active\n"
                )
                info_panel(text)
            except ImportError:
                info_panel("Lightpanda not installed. Using requests-based fetching instead.")
            except Exception as e:
                error_panel("BROWSER STATUS ERROR", str(e))
            return

        # Extract URL from command
        raw = command.split(maxsplit=1)[1].strip().strip('"\'')
        url = raw if raw.startswith("http") else None

        if not url:
            info_panel(
                "Usage: /web <url>\n"
                "  or   /fetch <url>\n"
                "  or   /scrape <url>\n"
                "Fetches and extracts page content (uses headless browser if available, falls back to requests)."
            )
            return

        spinner = AgentSpinner("Fetching page...")
        spinner.start()
        try:
            from lirox.agent.unified_executor import UnifiedExecutor
            ue = _executor_cache.get(f"{id(agent)}_auto") or UnifiedExecutor(provider="auto")
            result = ue._fetch_url_smart(url, query="")
            spinner.stop()

            if result:
                from lirox.ui.display import CLR_ACCENT
                console.print(f"\n[dim]URL: {url} | Method: {result.get('method', '?')}[/dim]")
                console.print(f"\n[{CLR_ACCENT}]{result['content'][:3000]}[/]")
                if len(result['content']) > 3000:
                    console.print(f"[dim]... ({len(result['content'])} total chars, truncated)[/dim]")
                console.print()
            else:
                error_panel("FETCH ERROR", "Could not retrieve content from that URL.")
        except Exception as e:
            error_panel("FETCH ERROR", str(e))
        return

    elif base == "/help":
        _show_animated_help()
    else:
        console.print(f"[dim]Unknown command: {base}. Type /help for assistance.[/dim]")

def _show_animated_help():
    """Phase 3: Animated help panel with categorised command reference."""
    from rich.table import Table
    from lirox.config import APP_VERSION

    table = Table(show_header=True, header_style="bold #FFC107", border_style="dim", padding=(0, 1))
    table.add_column("Command", style="bold white", no_wrap=True)
    table.add_column("Description", style="dim white")

    rows = [
        ("", "[bold #FFC107]─── CORE ────────────────────────[/]"),
        ("/help",          "Show this reference"),
        ("/profile",       "Agent identity + learning stats"),
        ("/models",        "List active LLM providers"),
        ("/add-api",       "Configure LLM API keys"),
        ("/reset",         "Purge all data and restart"),
        ("", ""),
        ("", "[bold #FFC107]─── RESEARCH ────────────────────[/]"),
        ('/research "Q"',  "Deep multi-source research"),
        ('/research "Q" --depth deep', "Extended 12-source research"),
        ("/sources",       "Show sources from last research"),
        ("/tier",          "Research tier & available APIs"),
        ("/add-search-api","Add Tavily / Serper / Exa keys"),
        ("", ""),
        ("", "[bold #FFC107]─── WEB & BROWSER ───────────────[/]"),
        ("/web <url>",     "Fetch page (headless or requests)"),
        ("/fetch <url>",   "Same as /web"),
        ("/scrape <url>",  "Extract tables/links from page"),
        ("/browser",       "Headless browser status"),
        ("", ""),
        ("", "[bold #FFC107]─── TASKS & MEMORY ──────────────[/]"),
        ("/memory",        "Memory core statistics"),
        ("/clear",         "Purge conversation history"),
        ("/trace",         "Low-level execution trace"),
        ("/reasoning",     "Last strategy reasoning"),
        ("/test",          "Run kernel diagnostics"),
        ("/update",        "Check & apply git updates"),
        ('/schedule "Q" --when X', "Defer a mission"),
        ("/run-task ID",   "Force-run a scheduled task"),
        ("/exit",          "Safely terminate the kernel"),
    ]

    for cmd, desc in rows:
        table.add_row(cmd, desc)

    from rich.panel import Panel
    from rich.box import ROUNDED
    from lirox.ui.display import console, CLR_LIROX
    console.print(Panel(
        table,
        title=f"[{CLR_LIROX}] LIROX v{APP_VERSION} — COMMAND REFERENCE [/]",
        border_style=CLR_LIROX,
        box=ROUNDED,
        padding=(1, 2),
    ))


def run_setup(agent):
    """Phase 3: Rich interactive onboarding wizard."""
    from lirox.ui.wizard import run_setup_wizard
    try:
        run_setup_wizard(agent.profile)
    except KeyboardInterrupt:
        # Graceful fallback if user hits Ctrl+C during setup
        console.print("\n  [dim]Setup interrupted. Using defaults. Run /add-api to add API keys.[/dim]")
        if not agent.profile.data.get("agent_name") or agent.profile.data.get("agent_name") == "Lirox":
            agent.profile.update("agent_name", "Lirox")
        if not agent.profile.data.get("user_name") or agent.profile.data.get("user_name") == "Operator":
            agent.profile.update("user_name", "Operator")

def run_api_setup():
    info_panel("API CHANNEL CONFIGURATION")
    print("Add keys to activate providers (empty to skip):")
    
    import getpass
    from dotenv import set_key
    from lirox.config import PROJECT_ROOT
    env_path = os.path.join(PROJECT_ROOT, ".env")
    
    providers = ["gemini", "groq", "openai", "openrouter", "deepseek", "anthropic", "nvidia"]
    
    for p in providers:
        # Use getpass to mask API keys during entry
        key = getpass.getpass(f"  {p.upper()} API KEY: ").strip()
        if key:
            env_var = f"{p.upper()}_API_KEY"
            set_key(env_path, env_var, key)
            os.environ[env_var] = key  # Update current process immediately
    
    success_message("Protocol updated securely. Provider mapping reloaded.")

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
