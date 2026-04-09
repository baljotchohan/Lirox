"""
Interactive skill creation wizard.
Creates reusable skills with full configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


class SkillCreationWizard:
    """Interactive skill creation wizard"""

    def run_interactive(self) -> dict | None:
        """Run complete interactive skill creation"""

        console.print("\n[cyan]⚙️  SKILL CREATION WIZARD[/]\n")
        console.print(
            "[dim]This will guide you through creating a reusable skill.[/]\n"
        )

        # Step 1: Skill Identity
        console.print("[bold]Step 1: Skill Identity[/]")
        skill_name = Prompt.ask("  Skill name", default="MySkill")
        skill_name = skill_name.replace(" ", "_").lower()

        description = Prompt.ask("  Description")

        # Step 2: Input Parameters
        console.print("\n[bold]Step 2: Input Parameters[/]")
        parameters = self._get_input_parameters()

        # Step 3: Output Configuration
        console.print("\n[bold]Step 3: Output Configuration[/]")
        output_type = Prompt.ask(
            "  Output type",
            choices=["string", "number", "boolean", "json", "list"],
            default="string",
        )

        # Step 4: Dependencies
        console.print("\n[bold]Step 4: Dependencies[/]")
        dependencies = Prompt.ask(
            "  Python packages needed (comma-separated, or leave blank)"
        )
        deps_list = [d.strip() for d in dependencies.split(",") if d.strip()]

        # Step 5: Implementation
        console.print("\n[bold]Step 5: Implementation[/]")
        console.print("  How should this skill work? (describe the logic)")
        implementation = Prompt.ask("  Implementation description")

        # Step 6: Test Cases
        console.print("\n[bold]Step 6: Test Cases[/]")
        test_cases = self._get_test_cases()

        # Step 7: Review
        console.print("\n[bold]Step 7: Review Configuration[/]")
        self._show_skill_summary(
            {
                "name": skill_name,
                "description": description,
                "parameters": len(parameters),
                "output_type": output_type,
                "dependencies": deps_list,
                "test_cases": len(test_cases),
            }
        )

        if not Confirm.ask("\n  Create this skill?", default=True):
            console.print("[yellow]Skill creation cancelled.[/]")
            return None

        # Create skill
        skill = self._create_skill(
            {
                "name": skill_name,
                "description": description,
                "parameters": parameters,
                "output_type": output_type,
                "dependencies": deps_list,
                "implementation": implementation,
                "test_cases": test_cases,
            }
        )

        console.print(f"\n[green]✅ Skill '{skill_name}' created![/]")
        saved_path = skill.get("_saved_path", "")
        if saved_path:
            console.print(f"   Saved to: [cyan]{saved_path}[/]")
        console.print(f"   Use it with: [bold]/use-skill {skill_name}[/]\n")
        return skill

    def _get_input_parameters(self) -> list:
        """Get input parameters"""

        parameters = []
        console.print("  Define parameters (leave blank to finish):")

        while True:
            param_name = Prompt.ask("    Parameter name (or skip)")
            if not param_name:
                break

            param_type = Prompt.ask(
                f"    Type for '{param_name}'",
                choices=["string", "number", "boolean", "list", "dict"],
                default="string",
            )

            required = Confirm.ask("    Required?", default=True)

            default = Prompt.ask("    Default value (or leave blank)")

            parameters.append(
                {
                    "name": param_name,
                    "type": param_type,
                    "required": required,
                    "default": default if default else None,
                }
            )

        return parameters

    def _get_test_cases(self) -> list:
        """Get test cases"""

        test_cases = []
        console.print("  Add test cases (leave blank to finish):")

        while True:
            console.print(f"\n  Test case #{len(test_cases) + 1}")
            input_data = Prompt.ask("    Input (JSON format)")
            if not input_data:
                break

            expected_output = Prompt.ask("    Expected output")

            test_cases.append(
                {
                    "input": input_data,
                    "expected_output": expected_output,
                }
            )

        return test_cases

    def _show_skill_summary(self, config: dict) -> None:
        """Show skill configuration summary"""

        table = Table(title="Skill Configuration", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for key, value in config.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        console.print(table)

    def _create_skill(self, config: dict) -> dict:
        """Create skill file and return skill data with its saved path."""

        import datetime

        from lirox.config import MIND_SKILLS_DIR

        skill_file = Path(MIND_SKILLS_DIR) / f"{config['name']}.json"
        skill_file.parent.mkdir(parents=True, exist_ok=True)

        skill_data = {
            "name": config["name"],
            "description": config["description"],
            "parameters": config["parameters"],
            "output_type": config["output_type"],
            "dependencies": config["dependencies"],
            "implementation": config["implementation"],
            "test_cases": config["test_cases"],
            "created_at": str(datetime.datetime.now(datetime.timezone.utc)),
        }

        with open(skill_file, "w") as f:
            json.dump(skill_data, f, indent=2)

        skill_data["_saved_path"] = str(skill_file)
        return skill_data
