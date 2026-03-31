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

# --- Provider Calls ---

def openai_call(prompt, system_prompt=None, model="gpt-4o"):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: return "OpenAI API key missing."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": model, "messages": [{"role": "system", "content": system_prompt or DEFAULT_SYSTEM}, {"role": "user", "content": prompt}]}
    try:
        res = requests.post(url, headers=headers, json=data, timeout=30)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e: return f"OpenAI Error: {str(e)}"

def gemini_call(prompt, system_prompt=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "Gemini API key missing."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=system_prompt or DEFAULT_SYSTEM)
        return model.generate_content(prompt).text
    except Exception as e: return f"Gemini Error: {str(e)}"

def groq_call(prompt, system_prompt=None, model="llama-3.3-70b-versatile"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return "Groq API key missing."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": model, "messages": [{"role": "system", "content": system_prompt or DEFAULT_SYSTEM}, {"role": "user", "content": prompt}]}
    try:
        res = requests.post(url, headers=headers, json=data, timeout=30)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e: return f"Groq Error: {str(e)}"

def openrouter_call(prompt, system_prompt=None, model="mistralai/mistral-7b-instruct:free"):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: return "OpenRouter API key missing."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": model, "messages": [{"role": "system", "content": system_prompt or DEFAULT_SYSTEM}, {"role": "user", "content": prompt}]}
    try:
        res = requests.post(url, headers=headers, json=data, timeout=30)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e: return f"OpenRouter Error: {str(e)}"

def deepseek_call(prompt, system_prompt=None, model="deepseek-chat"):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key: return "DeepSeek API key missing."
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": model, "messages": [{"role": "system", "content": system_prompt or DEFAULT_SYSTEM}, {"role": "user", "content": prompt}]}
    try:
        res = requests.post(url, headers=headers, json=data, timeout=30)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e: return f"DeepSeek Error: {str(e)}"

# --- Routing & Helpers ---

TASK_KEYWORDS = ["create", "build", "run", "install", "download", "execute", "pip", "npm", "search", "lookup", "research", "set up", "write a script", "generate a file", "make a folder", "mkdir", "open", "launch", "deploy"]
RESEARCH_KEYWORDS = ["who is", "what is", "explain", "how does", "why does", "tell me about", "research", "find out"]

def is_error_response(text):
    if not text: return True
    lowered = text.strip().lower()
    patterns = ["api key missing", "unknown provider", "request timed out", "error:", " error: "]
    return any(p in lowered for p in patterns)

def available_providers():
    mapping = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}
    return [name for name, env_var in mapping.items() if os.getenv(env_var)]

def provider_has_key(provider):
    return provider.lower() in available_providers()

def pick_default_provider():
    avail = available_providers()
    priority = ["gemini", "groq", "openrouter", "openai", "deepseek"]
    for p in priority:
        if p in avail: return p
    return "openai"

def smart_router(prompt):
    avail = available_providers()
    lowered = prompt.lower()
    if any(k in lowered for k in ["code", "script", "terminal", "run"]) and "groq" in avail:
        return "groq"
    if any(k in lowered for k in RESEARCH_KEYWORDS) and "openrouter" in avail:
        return "openrouter"
    return pick_default_provider()

def is_task_request(user_input, provider="auto"):
    lowered = user_input.lower()
    if any(k in lowered for k in TASK_KEYWORDS): return True
    try:
        check_prompt = f"Does this user message require executing terminal commands or creating files? Reply ONLY with yes or no.\n\nMessage: {user_input}"
        result = generate_response(check_prompt, "auto", system_prompt="You are a classifier. Reply only with yes or no.")
        return "yes" in result.strip().lower()
    except: return False

def generate_response(prompt, provider="auto", system_prompt=None):
    if provider == "auto":
        provider = smart_router(prompt)
    
    provider = provider.lower().strip("[]'\" ")
    if not provider_has_key(provider):
        fallback = pick_default_provider()
        if fallback == provider: return f"No API keys configured. Please add a key for {provider}."
        provider = fallback

    if provider == "openai": return openai_call(prompt, system_prompt)
    if provider == "gemini": return gemini_call(prompt, system_prompt)
    if provider == "groq": return groq_call(prompt, system_prompt)
    if provider == "openrouter": return openrouter_call(prompt, system_prompt)
    if provider == "deepseek": return deepseek_call(prompt, system_prompt)
    return f"Unknown provider: {provider}"
