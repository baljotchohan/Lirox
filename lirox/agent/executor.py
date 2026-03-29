from lirox.tools.terminal import run_command
from lirox.utils.llm import generate_response

class Executor:
    def execute_plan(self, steps, provider="openai"):
        results = []
        for step in steps:
            print(f"Executing: {step}")
            
            # Simple decision: If "run", "create", "install" is in step, it's a command
            lowered = step.lower()
            if any(k in lowered for k in ["run", "create", "install", "directory", "folder", "mkdir", "cat"]):
                # Try to extract the command from the step
                # A smarter agent would use the LLM to extract the command
                command_prompt = f"Extract the terminal command to execute from this step: '{step}'. Return ONLY the command."
                command = generate_response(command_prompt, provider).strip("`\"' ")
                
                print(f"Command: {command}")
                result = run_command(command)
            else:
                # Normal reasoning step
                result = generate_response(f"Step: {step}. Context: {results}. Provide a concise result.", provider)
            
            results.append(f"Step Result: {result}")
            print(f"Result: {result[:100]}...")
            
        return "\n".join(results)
