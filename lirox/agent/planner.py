from lirox.utils.llm import generate_response

class Planner:
    def __init__(self, provider="openai"):
        self.provider = provider

    def set_provider(self, provider):
        self.provider = provider

    def create_plan(self, goal, system_prompt=None):
        prompt = (
            f"Break down the following goal into clear, numbered steps for an AI agent to execute. "
            f"Each step should be a single, concrete action. "
            f"Return ONLY the numbered list, one step per line.\n\n"
            f"Goal: {goal}\n\n"
            f"Steps:"
        )
        response = generate_response(prompt, self.provider, system_prompt=system_prompt)
        steps = [
            s.strip() for s in response.split('\n')
            if s.strip() and (s.strip()[0].isdigit() or s.strip().startswith("-"))
        ]
        # Clean up step numbers/prefixes
        cleaned = []
        for step in steps:
            # Remove leading numbers/dots/dashes
            item = step.lstrip('0123456789.- ')
            if item:
                cleaned.append(item)
        
        return cleaned if cleaned else [response]
