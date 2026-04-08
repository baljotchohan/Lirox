"""
Interactive agent creation with full questionnaire.
Creates production-ready agents with all necessary configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


class AgentCreationWizard:
    """Interactive agent creation wizard"""

    def run_interactive(self) -> dict | None:
        """Run complete interactive agent creation"""

        console.print("\n[cyan]🤖 AGENT CREATION WIZARD[/]\n")
        console.print("[dim]This will guide you through creating a custom agent.[/]\n")

        # Step 1: Agent Identity
        console.print("[bold]Step 1: Agent Identity[/]")
        agent_name = Prompt.ask("  Agent name", default="MyAgent")
        agent_name = agent_name.replace(" ", "_").lower()

        # Step 2: Specialization
        console.print("\n[bold]Step 2: Specialization[/]")
        console.print("  What will this agent specialize in?")
        specialization = Prompt.ask("  Specialization", default="general tasks")

        # Step 3: Description
        console.print("\n[bold]Step 3: Description[/]")
        description = Prompt.ask("  Agent description", default="A custom agent")

        # Step 4: API Keys
        console.print("\n[bold]Step 4: API Keys[/]")
        api_keys = self._get_api_keys(description)

        # Step 5: Capabilities
        console.print("\n[bold]Step 5: Capabilities[/]")
        capabilities = self._select_capabilities()

        # Step 6: Response Format
        console.print("\n[bold]Step 6: Response Format[/]")
        response_format = Prompt.ask(
            "  Response format",
            choices=["concise", "balanced", "detailed"],
            default="balanced",
        )

        # Step 7: Memory Settings
        console.print("\n[bold]Step 7: Memory Settings[/]")
        memory_limit_str = Prompt.ask("  Memory buffer size", default="100")
        try:
            memory_limit = int(memory_limit_str)
        except ValueError:
            memory_limit = 100

        # Step 8: Custom System Prompt
        console.print("\n[bold]Step 8: System Prompt (optional)[/]")
        use_custom = Confirm.ask("  Use custom system prompt?", default=False)
        system_prompt = ""
        if use_custom:
            system_prompt = Prompt.ask("  System prompt (can be multi-line)")

        # Step 9: Verify Configuration
        console.print("\n[bold]Step 9: Verify Configuration[/]")
        self._show_summary(
            {
                "name": agent_name,
                "specialization": specialization,
                "description": description,
                "api_keys": list(api_keys.keys()),
                "capabilities": capabilities,
                "format": response_format,
                "memory": memory_limit,
                "system_prompt": (
                    system_prompt[:50] + "..." if system_prompt else "(default)"
                ),
            }
        )

        if not Confirm.ask("\n  Create this agent?", default=True):
            console.print("[yellow]Agent creation cancelled.[/]")
            return None

        # Create agent
        agent = self._create_agent(
            {
                "name": agent_name,
                "specialization": specialization,
                "description": description,
                "api_keys": api_keys,
                "capabilities": capabilities,
                "format": response_format,
                "memory": memory_limit,
                "system_prompt": system_prompt,
            }
        )

        console.print(f"\n[green]✓ Agent '{agent_name}' created successfully![/]\n")
        return agent

    def _get_api_keys(self, description: str) -> dict:
        """Detect and get required API keys"""

        api_keywords = {
            "search": ["groq", "openai", "gemini"],
            "research": ["openrouter", "anthropic"],
            "code": ["groq", "openai"],
            "analysis": ["anthropic", "gemini"],
        }

        suggested_apis: list[str] = []
        for keyword, apis in api_keywords.items():
            if keyword.lower() in description.lower():
                suggested_apis.extend(apis)

        console.print("  Required API providers:")
        selected_apis: dict = {}

        for api in set(suggested_apis):
            if Confirm.ask(f"    Use {api}?", default=True):
                key = Prompt.ask(f"    {api.upper()} API key", password=True)
                if key:
                    selected_apis[api] = key

        return selected_apis

    def _select_capabilities(self) -> list:
        """Select agent capabilities"""

        capabilities = [
            ("web_search", "Web search & browsing"),
            ("file_io", "Read/write files"),
            ("desktop", "Desktop control"),
            ("code", "Code generation & execution"),
            ("analysis", "Data analysis"),
            ("planning", "Task planning"),
        ]

        console.print("  Select capabilities:")
        selected = []

        for cap_id, cap_name in capabilities:
            if Confirm.ask(f"    {cap_name}?", default=True):
                selected.append(cap_id)

        return selected

    def _show_summary(self, config: dict) -> None:
        """Show configuration summary"""

        table = Table(title="Agent Configuration Summary", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for key, value in config.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        console.print(table)

    def _create_agent(self, config: dict) -> dict:
        """Create agent with configuration"""

        import datetime

        from lirox.config import MIND_AGENTS_DIR

        agent_file = Path(MIND_AGENTS_DIR) / f"{config['name']}.json"
        agent_file.parent.mkdir(parents=True, exist_ok=True)

        agent_data = {
            "name": config["name"],
            "specialization": config["specialization"],
            "description": config.get("description", ""),
            "capabilities": config["capabilities"],
            "response_format": config["format"],
            "memory_limit": config["memory"],
            "api_keys": list(config["api_keys"].keys()),
            "system_prompt": config["system_prompt"],
            "created_at": str(datetime.datetime.now(datetime.timezone.utc)),
        }

        with open(agent_file, "w") as f:
            json.dump(agent_data, f, indent=2)

        return agent_data
