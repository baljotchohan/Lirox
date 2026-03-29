import os
import requests
import google.generativeai as genai

DEFAULT_SYSTEM = "You are Lirox, a helpful and concise personal AI agent."

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

def smart_router(prompt):
    """
    Heuristic-first router.
    Groq = fast tasks/code. OpenRouter = research/knowledge. OpenAI = default.
    """
    lowered = prompt.lower()
    if any(k in lowered for k in TASK_KEYWORDS):
        return "groq"
    if any(k in lowered for k in RESEARCH_KEYWORDS):
        return "openrouter"
    return "openai"

def is_task_request(user_input, provider="groq"):
    """
    Detects if the input requires planning/execution. Use keyword heuristic first.
    """
    lowered = user_input.lower()
    if any(k in lowered for k in TASK_KEYWORDS):
        return True
    
    # Ambiguous - ask the LLM (using fast provider)
    check_prompt = f"Does this user message require executing terminal commands or creating files? Reply ONLY with yes or no.\n\nMessage: {user_input}"
    result = generate_response(check_prompt, "groq")
    return "yes" in result.strip().lower()
