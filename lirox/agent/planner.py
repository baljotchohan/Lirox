from lirox.utils.llm import generate_response
import json

class Planner:
    def __init__(self, provider="openai"):
        self.provider = provider

    def create_plan(self, goal):
        prompt = f"""Break down the following goal into a numbered list of steps for an AI agent to execute.
Return only the list of steps, one per line. If no external tools are needed, just describe the reasoning.

Goal: {goal}

Plan format:
1. First step
2. Second step
...
"""
        response = generate_response(prompt, self.provider)
        
        # Parse the response into a list of steps
        steps = [s.strip() for s in response.split('\n') if s.strip() and (s.strip()[0].isdigit() or s.strip().startswith("-"))]
        return steps if steps else [response]

    def set_provider(self, provider):
        self.provider = provider
