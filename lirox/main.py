import sys
from lirox.agent.core import LiroxAgent
from lirox.utils.config_helper import run_setup_wizard

def main():
    print("\n" + "=" * 50)
    print("Welcome to Lirox v0.1: Your Local AI Agent")
    print("-" * 50)
    print("Options: /add-api (setup keys), /set model [provider], /clear, /exit\n")

    agent = LiroxAgent()

    while True:
        try:
            user_input = input("You > ").strip()
        except EOFError:
            break

        if not user_input:
            continue

        if user_input.lower() == "/exit":
            print("Goodbye!")
            break

        if user_input.lower() in ["/add-api", "/setup"]:
            is_new_default = run_setup_wizard()
            # Reload agent if provider changed
            if is_new_default:
                import os
                new_provider = os.getenv("DEFAULT_MODEL", "openai")
                agent.set_provider(new_provider)
                print(f"[*] Reloaded agent with new default provider: {new_provider}")
            continue

        if user_input.startswith("/set model"):
            model_name = user_input.replace("/set model", "").strip(" []'\"")
            if model_name:
                agent.set_provider(model_name)
                print(f"Model updated to: {model_name}")
            else:
                print("Usage: /set model [provider]")
            continue

        if user_input.startswith("/clear"):
            agent.memory.clear()
            print("[*] Memory cleared.")
            continue

        try:
            response = agent.process_input(user_input)
            print(f"\nAI: {response}\n")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
