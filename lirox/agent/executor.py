from lirox.tools.terminal import run_command
from lirox.utils.llm import generate_response
from lirox.ui.display import execute_panel, update_plan_step

# Keywords that suggest a terminal command is needed
COMMAND_TRIGGERS = [
    "run", "create", "install", "mkdir", "directory", "folder",
    "cat", "touch", "pip", "npm", "python", "execute", "launch", "open"
]

class Executor:
    def execute_plan(self, steps, provider="openai", system_prompt=None):
        results = []
        for i, step in enumerate(steps, 1):
            update_plan_step(i, step, status="progress")
            lowered = step.lower()

            if any(k in lowered for k in COMMAND_TRIGGERS):
                # Use LLM to extract the exact terminal command
                cmd_prompt = (
                    f"Extract the exact terminal command to execute from this step. "
                    f"Return ONLY the raw command. No explanation, no backticks, no extra text.\n\n"
                    f"Step: {step}"
                )
                command = generate_response(cmd_prompt, provider, system_prompt=system_prompt)
                command = command.strip().strip("`\"' ")
                
                # Double-check command isn't just "mkdir" etc. (sometimes LLMs return only the base cmd)
                if len(command.split()) == 1 and command not in ["ls", "pwd"]:
                    # Fallback to more direct extraction
                    pass 
                
                execute_panel(command)
                result = run_command(command)
            else:
                # Reasoning step — ask LLM to process it
                reasoning_prompt = (
                    f"Complete this task step and provide a concise result.\n\n"
                    f"Step: {step}\n"
                    f"Previous results: {results[-1] if results else 'None'}"
                )
                result = generate_response(reasoning_prompt, provider, system_prompt=system_prompt)

            update_plan_step(i, step, status="success")
            
            # Truncate result for log
            result_preview = result[:120] + "..." if len(result) > 120 else result
            results.append(f"Step {i} ({step}): {result}")

        return "\n\n".join(results)
