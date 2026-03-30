import os
import requests
import google.generativeai as genai

DEFAULT_SYSTEM = (
    "You are Lirox, a helpful and concise personal AI agent. "
    "Response formatting rules you must always follow: "
    "Never use asterisks (*) or markdown bold/italic formatting. "
    "Never use excessive bullet points. "
    "Write in clean, plain sentences and short paragraphs. "
    "Use numbered lists only when listing steps or options. "
    "Keep responses structured but natural — like a smart colleague talking to you, not a formatted document."
)

def openai_call(prompt, system_prompt=None, model="gpt-4o"):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OpenAI API key missing. Run /add-api to configure."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        return "Error: OpenAI request timed out."
    except Exception as e:
        return f"OpenAI Error: {str(e)}"

def gemini_call(prompt, system_prompt=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini API key missing. Run /add-api to configure."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=system_prompt or DEFAULT_SYSTEM
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini Error: {str(e)}"

def groq_call(prompt, system_prompt=None, model="llama-3.3-70b-versatile"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Groq API key missing. Run /add-api to configure."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        return "Error: Groq request timed out."
    except Exception as e:
        return f"Groq Error: {str(e)}"

def openrouter_call(prompt, system_prompt=None, model="mistralai/mistral-7b-instruct:free"):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "OpenRouter API key missing. Run /add-api to configure."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"OpenRouter Error: {str(e)}"

def deepseek_call(prompt, system_prompt=None, model="deepseek-chat"):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "DeepSeek API key missing. Run /add-api to configure."
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"DeepSeek Error: {str(e)}"

# Task and Research Keywords for fast routing heuristics
TASK_KEYWORDS = [
    "create", "build", "run", "install", "download", "execute", "pip install", "npm install",
    "search", "lookup", "research", "set up", "write a script", "generate a file", "make a folder",
    "mkdir", "open", "launch", "deploy"
]

RESEARCH_KEYWORDS = [
    "who is", "what is", "explain", "how does", "why does", "tell me about", "research", "find out"
]

# Patterns indicating the LLM returned an error string instead of a real response
ERROR_RESPONSE_PATTERNS = [
    "api key missing",
    "unknown provider",
    "request timed out",
    "error:",
    " error: ",
]


def is_error_response(text):
    """
    Detect if an LLM response is actually an error string.
    Returns True if the response looks like an error, not real content.
    """
    if not text:
        return True
    lowered = text.strip().lower()
    return any(p in lowered for p in ERROR_RESPONSE_PATTERNS)

def generate_response(prompt, provider="openai", system_prompt=None):
    """
    Central call. Always pass system_prompt from UserProfile for personalization.
    """
    provider = provider.lower().strip("[]'\" ")
    if provider == "openai":
        return openai_call(prompt, system_prompt)
    if provider == "gemini":
        return gemini_call(prompt, system_prompt)
    if provider == "groq":
        return groq_call(prompt, system_prompt)
    if provider == "openrouter":
        return openrouter_call(prompt, system_prompt)
    if provider == "deepseek":
        return deepseek_call(prompt, system_prompt)
    return f"Unknown provider: {provider}. Use: openai, gemini, groq, openrouter, deepseek"

def available_providers():
    """Returns list of providers with keys present in environment."""
    mapping = {
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY"
    }
    return [name for name, env_key in mapping.items() if os.getenv(env_key)]

def pick_default_provider():
    """
    Choose the best default provider based on key availability.
    Priority: gemini -> groq -> openrouter -> openai -> deepseek.
    """
    avail = available_providers()
    priority = ["gemini", "groq", "openrouter", "openai", "deepseek"]
    for p in priority:
        if p in avail:
            return p
    return "openai"  # Fallback if none found (will show error on call)

def smart_router(prompt):
    """
    Heuristic-first router with fallback based on key availability.
    """
    lowered = prompt.lower()
    avail = available_providers()
    
    # Priority logic:
    # 1. If task/code task → Groq
    # 2. If research → OpenRouter
    # 3. Else → Gemini (best free) or OpenAI
    
    if any(k in lowered for k in TASK_KEYWORDS) and "groq" in avail:
        return "groq"
    
    if any(k in lowered for k in RESEARCH_KEYWORDS) and "openrouter" in avail:
        return "openrouter"
    
    # Fallback to best available
    return pick_default_provider()

def is_task_request(user_input, provider="groq"):
    """
    Detects if the input requires planning/execution.
    Uses keyword heuristic first, then falls back to LLM if ambiguous.
    Hardened: never hangs or crashes — defaults to False on any error.
    """
    lowered = user_input.lower()
    if any(k in lowered for k in TASK_KEYWORDS):
        return True

    # Ambiguous — try asking the LLM (using fast provider)
    try:
        check_prompt = (
            f"Does this user message require executing terminal commands or creating files? "
            f"Reply ONLY with yes or no.\n\nMessage: {user_input}"
        )
        result = generate_response(check_prompt, "groq")
        if is_error_response(result):
            return False  # LLM errored — default to chat mode
        return "yes" in result.strip().lower()
    except Exception:
        return False  # Any failure → default to chat mode
