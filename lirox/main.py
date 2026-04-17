"""Lirox v2.0.0 — Main Entry Point

New commands: /think, /status, /train, /profile, /memory, /use-model,
              /backup, /export-memory, /import-memory
Removed:      /soul, /improve, /apply, /pending, /permissions,
              /ask-permission, /recall

Bug fixes in this version:
  BUG-1: LearningsStore no longer crashes on missing keys
  BUG-2: render_progress_indicator imported at module level in display.py
  BUG-3: PDF creation uses fpdf2 for real PDFs
  BUG-4: /think executes plans, not just returns text
  BUG-5: Background auto-training runs every 15 messages
  BUG-6: Better @agentname extraction
  BUG-7: Removed 5-tier permission system
  BUG-8: Sub-agents get full conversation context
"""
from __future__ import annotations

import os
import sys
import time
import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime

# ── Ensure package root on sys.path ──────────────────────────────────────────
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def _bootstrap_dependencies() -> None:
    """Check for and optionally install missing dependencies."""
    try:
        from lirox.utils.dependency_bootstrap import (
            missing_packages,
            install_missing_packages,
            required_package_map,
        )
        pkg_map = required_package_map()
        missing = missing_packages(pkg_map)
        if missing:
            print(f"[Lirox] Installing missing packages: {', '.join(missing)}")
            install_missing_packages(missing)
    except Exception:
        pass


def main() -> None:
    _bootstrap_dependencies()

    parser = argparse.ArgumentParser(
        prog="lirox",
        description="Lirox v2.0.0 — Intelligence as an Operating System",
    )
    parser.add_argument("--setup", action="store_true",
                        help="Run setup wizard")
    parser.add_argument("--version", action="store_true",
                        help="Print version and exit")
    parser.add_argument("--no-banner", action="store_true",
                        help="Skip the logo banner")
    parser.add_argument("query", nargs="*",
                        help="One-shot query (non-interactive)")
    args = parser.parse_args()

    if args.version:
        from lirox.config import APP_VERSION
        print(f"Lirox v{APP_VERSION}")
        return

    # ── Lazy imports (after bootstrap) ────────────────────────────────────────
    from lirox.config import APP_VERSION, DATA_DIR, BACKUPS_DIR
    from lirox.agent.profile import UserProfile
    from lirox.core.memory import LearningsStore, MemoryManager
    from lirox.core.background import BackgroundEngine
    from lirox.core.agent import UnifiedAgent
    from lirox.core.skills import SkillsManager
    from lirox.core.sub_agents import SubAgentsManager
    from lirox.memory.session_store import SessionStore
    from lirox.ui.display import (
        console, show_welcome, show_response, stream_response,
        show_thinking, show_step, show_error, show_success,
        show_status, show_memory, show_help, spinner,
    )
    from lirox.ui.wizard import run_setup_wizard

    # ── Initialize components ─────────────────────────────────────────────────
    profile      = UserProfile()
    learnings    = LearningsStore()
    memory       = MemoryManager()
    session_store = SessionStore()
    skills_mgr   = SkillsManager()
    agents_mgr   = SubAgentsManager()
    bg_engine    = BackgroundEngine(memory, learnings)

    agent = UnifiedAgent(
        profile=profile,
        learnings=learnings,
        memory=memory,
        session_store=session_store,
    )

    # Start background engine
    bg_engine.start()

    # ── Setup or welcome ──────────────────────────────────────────────────────
    if args.setup or not profile.is_setup():
        run_setup_wizard(profile)
    elif not args.no_banner:
        show_welcome()

    # ── One-shot mode ─────────────────────────────────────────────────────────
    if args.query:
        query = " ".join(args.query)
        _handle_query(query, agent, profile, learnings, memory, session_store,
                      bg_engine, skills_mgr, agents_mgr,
                      stream_response, show_thinking, show_step, show_error)
        return

    # ── Interactive REPL ──────────────────────────────────────────────────────
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
        pt_session = PromptSession(history=InMemoryHistory())

        def get_input(prompt_text: str) -> str:
            return pt_session.prompt(prompt_text)
    except ImportError:
        def get_input(prompt_text: str) -> str:
            return input(prompt_text)

    agent_name = profile.data.get("agent_name", "Lirox")
    prompt_text = f"\n[{agent_name}] > "

    while True:
        try:
            user_input = get_input(prompt_text).strip()
        except (KeyboardInterrupt, EOFError):
            console.print(f"\n[dim]Bye! 👋[/]")
            bg_engine.stop()
            break

        if not user_input:
            continue

        # ── Command dispatch ──────────────────────────────────────────────────
        result = _handle_command(
            user_input, profile, learnings, memory, session_store,
            bg_engine, skills_mgr, agents_mgr,
            show_status, show_memory, show_help, show_error, show_success,
            console, DATA_DIR, BACKUPS_DIR,
        )

        if result == "EXIT":
            console.print("[dim]Bye! 👋[/]")
            bg_engine.stop()
            break
        elif result == "HANDLED":
            continue  # command was handled, loop back
        else:
            # Route to agent
            _handle_query(
                user_input, agent, profile, learnings, memory, session_store,
                bg_engine, skills_mgr, agents_mgr,
                stream_response, show_thinking, show_step, show_error,
            )


# ── Command Handler ───────────────────────────────────────────────────────────

def _handle_command(
    user_input: str, profile, learnings, memory, session_store,
    bg_engine, skills_mgr, agents_mgr,
    show_status, show_memory, show_help, show_error, show_success,
    console, data_dir: str, backups_dir: str,
) -> str:
    """
    Handle slash commands. Returns:
      "EXIT"    — user wants to quit
      "HANDLED" — command was processed
      None      — not a command, treat as query
    """
    cmd   = user_input.strip()
    lower = cmd.lower()

    # Exit
    if lower in ("/exit", "/quit", "exit", "quit"):
        return "EXIT"

    # Help
    if lower == "/help":
        show_help()
        return "HANDLED"

    # Setup
    if lower == "/setup":
        from lirox.ui.wizard import run_setup_wizard
        run_setup_wizard(profile)
        return "HANDLED"

    # Status
    if lower == "/status":
        show_status(profile, learnings, memory, bg_engine)
        return "HANDLED"

    # Profile
    if lower == "/profile":
        console.print(profile.summary())
        return "HANDLED"

    # Memory
    if lower == "/memory":
        show_memory(learnings)
        return "HANDLED"

    # Train
    if lower == "/train":
        console.print("[dim]Training… extracting knowledge from conversations…[/]")
        result = bg_engine.manual_train()
        if "error" in result:
            show_error(f"Training failed: {result['error']}")
        elif "message" in result:
            console.print(f"[dim]{result['message']}[/]")
        else:
            show_success(
                f"Training complete: +{result.get('facts', 0)} facts, "
                f"+{result.get('topics', 0)} topics, "
                f"+{result.get('projects', 0)} projects"
            )
        return "HANDLED"

    # Use-model
    if lower.startswith("/use-model"):
        parts = cmd.split(None, 1)
        if len(parts) < 2:
            console.print("[dim]Usage: /use-model <provider>[/]")
            console.print("[dim]Providers: groq, gemini, openai, anthropic, openrouter, ollama[/]")
        else:
            provider = parts[1].strip().lower()
            os.environ["_LIROX_PINNED_MODEL"] = provider
            show_success(f"Using model provider: {provider}")
        return "HANDLED"

    # Add skill
    if lower.startswith("/add-skill"):
        parts = cmd.split(None, 1)
        if len(parts) < 2:
            show_error("Usage: /add-skill <description of what the skill should do>")
            return "HANDLED"
        desc = parts[1].strip()
        console.print(f"[dim]Generating skill: {desc}…[/]")
        result = skills_mgr.add_skill(desc)
        if "error" in result:
            show_error(f"Skill creation failed: {result['error']}")
        else:
            show_success(f"Skill created: {result['name']} → {result['file']}")
        return "HANDLED"

    # Skills list
    if lower == "/skills":
        console.print(skills_mgr.format_list())
        return "HANDLED"

    # Use skill
    if lower.startswith("/use-skill"):
        parts = cmd.split(None, 1)
        if len(parts) < 2:
            show_error("Usage: /use-skill <number or name>")
            return "HANDLED"
        name_or_idx = parts[1].strip()
        console.print(f"[dim]Running skill: {name_or_idx}…[/]")
        result = skills_mgr.run_skill(name_or_idx)
        console.print(result)
        return "HANDLED"

    # Add agent
    if lower.startswith("/add-agent"):
        parts = cmd.split(None, 1)
        if len(parts) < 2:
            show_error("Usage: /add-agent <description of agent specialization>")
            return "HANDLED"
        desc = parts[1].strip()
        console.print(f"[dim]Generating agent: {desc}…[/]")
        result = agents_mgr.add_agent(desc)
        if "error" in result:
            show_error(f"Agent creation failed: {result['error']}")
        else:
            show_success(
                f"Agent created: @{result['name']} → {result['file']}\n"
                f"  Use: @{result['name']} <your message>"
            )
        return "HANDLED"

    # Agents list
    if lower == "/agents":
        console.print(agents_mgr.format_list())
        return "HANDLED"

    # History
    if lower == "/history":
        console.print(session_store.format_history())
        return "HANDLED"

    # Reset session
    if lower == "/reset":
        session_store.new_session()
        show_success("Session reset.")
        return "HANDLED"

    # Backup
    if lower == "/backup":
        result = _do_backup(data_dir, backups_dir)
        if result:
            show_success(f"Backup created: {result}")
        else:
            show_error("Backup failed.")
        return "HANDLED"

    # Export memory
    if lower == "/export-memory":
        result = _do_export_memory(learnings, data_dir)
        show_success(f"Memory exported: {result}")
        return "HANDLED"

    # Import memory
    if lower.startswith("/import-memory"):
        parts = cmd.split(None, 1)
        if len(parts) < 2:
            show_error("Usage: /import-memory <path-to-json-file>")
            return "HANDLED"
        path = parts[1].strip()
        result = _do_import_memory(learnings, path, show_success, show_error)
        return "HANDLED"

    # Not a command
    return None


# ── Query Handler ─────────────────────────────────────────────────────────────

def _handle_query(
    user_input: str, agent, profile, learnings, memory, session_store,
    bg_engine, skills_mgr, agents_mgr,
    stream_response, show_thinking, show_step, show_error,
) -> None:
    """Route user input to the appropriate handler."""
    from lirox.core.sub_agents import SubAgentsManager

    # BUG-6 FIX: better @agentname extraction
    mention = SubAgentsManager.extract_agent_mention(user_input)
    if mention:
        agent_name, query = mention
        full_context = session_store.get_context()
        # BUG-8 FIX: pass full_context to sub-agent
        result = agents_mgr.route_to_agent(agent_name, query, full_context)
        stream_response(result, agent_name=f"@{agent_name}")
        session_store.current().add("user", user_input)
        session_store.current().add("assistant", result)
        memory.save_exchange(user_input, result)
        session_store.save_current()
        bg_engine.tick()
        return

    # BUG-4 FIX: /think executes full pipeline with deep=True
    deep = False
    query = user_input
    if user_input.lower().startswith("/think "):
        deep  = True
        query = user_input[7:].strip()
        if not query:
            show_error("Usage: /think <your question or task>")
            return

    # Add to session
    session_store.current().add("user", query)

    # Run agent pipeline
    response_text = ""
    try:
        for event in agent.run(query, deep=deep):
            etype = event.get("type")
            if etype == "thinking":
                show_thinking(event.get("content", ""))
            elif etype == "step":
                show_step(event.get("action", ""), event.get("result", ""))
            elif etype == "response":
                content = event.get("content", "")
                agent_name = profile.data.get("agent_name", "Lirox")
                stream_response(content, agent_name=agent_name)
                response_text = content
            elif etype == "done":
                response_text = event.get("response", response_text)
            elif etype == "error":
                show_error(event.get("content", "Unknown error"))
    except KeyboardInterrupt:
        from lirox.ui.display import console
        console.print("\n[dim]Interrupted.[/]")
        return
    except Exception as e:
        show_error(f"Agent error: {e}")
        return

    # Persist
    if response_text:
        session_store.current().add("assistant", response_text)
        memory.save_exchange(query, response_text)
        session_store.save_current()
        # BUG-5 FIX: tick() triggers auto-training every 15 messages
        bg_engine.tick()


# ── Backup / Export / Import Helpers ─────────────────────────────────────────

def _do_backup(data_dir: str, backups_dir: str) -> str:
    """Create a timestamped backup of the data directory."""
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst     = os.path.join(backups_dir, f"backup_{ts}")
    try:
        shutil.copytree(data_dir, dst)
        return dst
    except Exception as e:
        return None


def _do_export_memory(learnings, data_dir: str) -> str:
    """Export memory to a JSON file in the data directory."""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(data_dir, f"memory_export_{ts}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(learnings.export_json())
        return path
    except Exception as e:
        return f"Error: {e}"


def _do_import_memory(learnings, path: str, show_success, show_error) -> None:
    """Import memory from a JSON file."""
    expanded = str(Path(path).expanduser())
    if not os.path.exists(expanded):
        show_error(f"File not found: {path}")
        return
    try:
        with open(expanded, "r", encoding="utf-8") as f:
            raw = f.read()
        if learnings.import_json(raw):
            show_success(f"Memory imported from: {path}")
        else:
            show_error("Failed to parse JSON file.")
    except Exception as e:
        show_error(f"Import error: {e}")


if __name__ == "__main__":
    main()
