import os
from dotenv import set_key

# Mapping of user-friendly names to .env keys
PROVIDERS = {
    "1": ("OpenAI",      "OPENAI_API_KEY"),
    "2": ("Gemini",      "GEMINI_API_KEY"),
    "3": ("OpenRouter",  "OPENROUTER_API_KEY"),
    "4": ("Groq",        "GROQ_API_KEY"),
    "5": ("DeepSeek",    "DEEPSEEK_API_KEY"),
    "6": ("NVIDIA NIM",  "NVIDIA_API_KEY"),
    "7": ("Anthropic",   "ANTHROPIC_API_KEY"),
}

def show_config_status():
    print("\n--- Current Configuration Status ---")
    for idx, (name, env_key) in PROVIDERS.items():
        key_val = os.getenv(env_key)
        status = "✅ Set" if key_val and len(key_val) > 10 else "❌ Not Set"
        print(f"[{idx}] {name:12} : {status}")
    print("------------------------------------\n")

def run_setup_wizard():
    """Interactive flow to add/update API keys."""
    from lirox.config import PROJECT_ROOT
    import shutil
    
    show_config_status()
    
    choice = input("Enter the number of the provider to configure (or 'q' to quit): ").strip()
    
    if choice.lower() == 'q':
        return False
    
    if choice in PROVIDERS:
        name, env_key = PROVIDERS[choice]
        print(f"\nConfiguring {name}...")
        new_key = input(f"Paste your {name} API Key: ").strip()
        
        if new_key:
            # Update .env file — anchored to PROJECT_ROOT
            env_path = os.path.join(PROJECT_ROOT, ".env")
            if not os.path.exists(env_path):
                # Fallback to .env.example copy if .env doesn't exist
                example_path = os.path.join(PROJECT_ROOT, ".env.example")
                if os.path.exists(example_path):
                    shutil.copy(example_path, env_path)
                else:
                    open(env_path, 'a').close()
            
            set_key(env_path, env_key, new_key)
            
            # Update current process environment
            os.environ[env_key] = new_key
            
            print(f"\n[SUCCESS] {name} API Key updated successfully!")
            
            # Ask if they want to set as default
            make_default = input(f"Set {name} as your default model provider? (y/n): ").strip().lower()
            if make_default == 'y':
                set_key(env_path, "DEFAULT_MODEL", name.lower())
                os.environ["DEFAULT_MODEL"] = name.lower()
                print(f"[SUCCESS] {name} is now your default provider.")
                return True
        else:
            print("\n[SKIP] No key provided. No changes made.")
    else:
        print("\n[ERROR] Invalid choice.")
        
    return False
