"""
Lirox v0.5 — LLM Utility Layer

Provider support: Gemini, Groq, OpenAI, OpenRouter, DeepSeek, NVIDIA, Anthropic
Features:
  - Smart provider routing based on task type
  - Automatic fallback chain: primary → secondary → tertiary
  - is_task_request caching (per input hash) to avoid redundant LLM calls
  - 60-second timeout (up from 30s) for long research tasks
  - generate_response_stream() generator for SSE/WebSocket streaming
  - Anthropic Claude provider (claude-3-5-haiku for speed, claude-opus for heavy)
"""

import os
import hashlib
import requests
from typing import List, Dict, Optional, Generator

DEFAULT_SYSTEM = (
    "You are Lirox, a premium autonomous AI agent designed for high-performance research and systems execution. "
    "MANDATORY FORMATTING RULES:\n"
    "1. CLEAN & STRUCTURED: Never output a wall of text. Use logical sections.\n"
    "2. HIERARCHY: Use Markdown headers (#, ##) to label different parts of your response.\n"
    "3. DATA POINTS: Use bullet points and numbered lists for all sequences and features.\n"
    "4. EMPHASIS: Use bold (**text**) for critical terms, agent names, or results.\n"
    "5. TECHNICAL: Use code blocks (`text`) for paths, commands, and file names.\n"
    "6. TONE: Sophisticated, competent, and direct. Avoid conversational fluff."
)

# LLM call timeout — 60s to support long research tasks
_LLM_TIMEOUT = 60

# ─── is_task_request Cache ───────────────────────────────────────────────────
_task_cache: Dict[str, bool] = {}

def _hash_prompt(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()[:16]


# ─── Provider Implementations ─────────────────────────────────────────────────

def openai_call(prompt, system_prompt=None, model="gpt-4o"):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OpenAI API key missing."
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
        res = requests.post(url, headers=headers, json=data, timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenAI Error: {str(e)}"


def gemini_call(prompt, system_prompt=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini API key missing."
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        
        # In the new SDK, system_instruction is passed to generate_content
        # or as a config in some versions. Let's use the standard config way.
        config = types.GenerateContentConfig(
            system_instruction=system_prompt or DEFAULT_SYSTEM,
            temperature=0.7,
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", # Upgrade to 2.0 while we are at it if they have it
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as e:
        # Fallback to gemini-1.5-flash if 2.0 is not available
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=config
            )
            return response.text
        except Exception:
            return f"Gemini Error: {str(e)}"


def groq_call(prompt, system_prompt=None, model="llama-3.3-70b-versatile"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Groq API key missing."
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
        res = requests.post(url, headers=headers, json=data, timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Groq Error: {str(e)}"


def openrouter_call(prompt, system_prompt=None, model="mistralai/mistral-7b-instruct:free"):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "OpenRouter API key missing."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://lirox.ai",
        "X-Title": "Lirox Agent OS"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        res = requests.post(url, headers=headers, json=data, timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenRouter Error: {str(e)}"


def deepseek_call(prompt, system_prompt=None, model="deepseek-chat"):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "DeepSeek API key missing."
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
        res = requests.post(url, headers=headers, json=data, timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"DeepSeek Error: {str(e)}"


def nvidia_call(prompt, system_prompt=None, model="meta/llama-3.1-405b-instruct"):
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return "NVIDIA API key missing."
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        res = requests.post(url, headers=headers, json=data, timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"NVIDIA Error: {str(e)}"


def anthropic_call(prompt, system_prompt=None, model="claude-3-5-haiku-20241022"):
    """
    Anthropic Claude provider.
    Uses the raw HTTP API so the `anthropic` SDK package is optional.
    Falls back to SDK if available.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Anthropic API key missing."

    # Try SDK first (cleaner)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt or DEFAULT_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except ImportError:
        pass  # SDK not installed — fall through to raw HTTP
    except Exception as e:
        return f"Anthropic SDK Error: {str(e)}"

    # Raw HTTP fallback
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    data = {
        "model": model,
        "max_tokens": 4096,
        "system": system_prompt or DEFAULT_SYSTEM,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        res = requests.post(url, headers=headers, json=data, timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["content"][0]["text"]
    except Exception as e:
        return f"Anthropic Error: {str(e)}"


# ─── Provider Registry & Routing ─────────────────────────────────────────────

_PROVIDER_ENV_MAP = {
    "gemini":    "GEMINI_API_KEY",
    "groq":      "GROQ_API_KEY",
    "openrouter":"OPENROUTER_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "deepseek":  "DEEPSEEK_API_KEY",
    "nvidia":    "NVIDIA_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

_PROVIDER_PRIORITY = ["groq", "openrouter", "gemini", "anthropic", "nvidia", "openai", "deepseek"]

TASK_KEYWORDS = [
    "create", "build", "run", "install", "download", "execute", "pip", "npm",
    "search", "lookup", "research", "set up", "write a script", "generate a file",
    "make a folder", "mkdir", "open", "launch", "deploy", "find", "analyze"
]

RESEARCH_KEYWORDS = [
    "who is", "what is", "explain", "how does", "why does",
    "tell me about", "research", "find out", "what are", "compare"
]


def available_providers() -> List[str]:
    return [name for name, env_var in _PROVIDER_ENV_MAP.items() if os.getenv(env_var)]


def provider_has_key(provider: str) -> bool:
    return provider.lower() in available_providers()


def pick_default_provider() -> Optional[str]:
    avail = available_providers()
    for p in _PROVIDER_PRIORITY:
        if p in avail:
            return p
    return None


def smart_router(prompt: str) -> Optional[str]:
    """Route a prompt to the best available provider based on content type."""
    avail = available_providers()
    lowered = prompt.lower()

    if any(k in lowered for k in ["complex", "reason", "heavy", "think deep", "analyze"]) and "anthropic" in avail:
        return "anthropic"
    if any(k in lowered for k in ["complex", "reason", "heavy", "think deep"]) and "nvidia" in avail:
        return "nvidia"
    if any(k in lowered for k in ["code", "script", "terminal", "run", "debug"]) and "groq" in avail:
        return "groq"
    if any(k in lowered for k in RESEARCH_KEYWORDS) and "openrouter" in avail:
        return "openrouter"

    return pick_default_provider()


def is_error_response(text: str) -> bool:
    if not text:
        return True
    lowered = text.strip().lower()
    patterns = ["api key missing", "unknown provider", "request timed out", "error: ", " error: "]
    return any(p in lowered for p in patterns)


def is_task_request(user_input: str, provider: str = "auto") -> bool:
    """
    Classify whether a user message requires agentic task execution.
    Results are cached by input hash to avoid redundant LLM calls.
    """
    lowered = user_input.lower()

    # Fast keyword path — no LLM call needed
    if any(k in lowered for k in TASK_KEYWORDS):
        return True

    # Pure question / chat heuristics — also fast path
    question_starters = ["who ", "what ", "why ", "when ", "how ", "is ", "are ", "do ", "does "]
    if any(lowered.startswith(s) for s in question_starters) and len(user_input.split()) < 15:
        return False

    # LLM-based classification (with cache)
    cache_key = _hash_prompt(user_input)
    if cache_key in _task_cache:
        return _task_cache[cache_key]

    if not available_providers():
        return False

    try:
        check_prompt = (
            "Does this user message require executing terminal commands, "
            "creating files, or running multi-step tasks? Reply ONLY with yes or no.\n\n"
            f"Message: {user_input}"
        )
        result = generate_response(
            check_prompt, "auto",
            system_prompt="You are a classifier. Reply only with 'yes' or 'no'."
        )
        decision = "yes" in result.strip().lower()
        _task_cache[cache_key] = decision
        return decision
    except Exception:
        return False


# ─── Core Response Generation ────────────────────────────────────────────────

def generate_response(prompt: str, provider: str = "auto", system_prompt: str = None) -> str:
    """
    Generate a response from the best available provider.
    Includes automatic fallback chain if primary fails.
    """
    if provider == "auto":
        provider = smart_router(prompt)

    if provider is None:
        return (
            "No API keys are configured. Please add at least one key:\n"
            "  • CLI: run /add-api\n"
            "  • Web UI: go to System Settings → API Keys\n"
            "  • Manual: add keys to your .env file"
        )

    provider = provider.lower().strip("[]'\" ")
    if not provider_has_key(provider):
        fallback = pick_default_provider()
        if fallback is None:
            return "No API keys configured. Please add a key via /add-api or in the .env file."
        if fallback == provider:
            return f"No API key configured for: {provider}"
        provider = fallback

    # Primary attempt
    response = _call_provider(provider, prompt, system_prompt)

    # Execution-time fallback chain
    if is_error_response(response):
        avail = available_providers()
        fallbacks = [p for p in _PROVIDER_PRIORITY if p in avail and p != provider]
        for fb in fallbacks:
            retry = _call_provider(fb, prompt, system_prompt)
            if not is_error_response(retry):
                return retry

    return response


def generate_response_stream(prompt: str, provider: str = "auto", system_prompt: str = None) -> Generator[str, None, None]:
    """
    Generator that yields response chunks for streaming (SSE/WebSocket).
    Currently yields the full response as a single chunk.
    Per-provider streaming can be added here incrementally.
    """
    response = generate_response(prompt, provider=provider, system_prompt=system_prompt)
    # Yield in chunks of ~50 chars to simulate streaming
    chunk_size = 50
    for i in range(0, len(response), chunk_size):
        yield response[i:i + chunk_size]


def _call_provider(provider: str, prompt: str, system_prompt: Optional[str]) -> str:
    """Route to the correct provider function with rate and resource limits."""
    from lirox.utils.rate_limiter import api_limiter, sys_monitor
    import time
    
    # Enforce API rate limits
    api_limiter.wait_if_needed()
    
    # Enforce system resource limits
    while not sys_monitor.check_resources():
        time.sleep(5)
        
    # Record this call
    api_limiter.record_call()

    if provider == "openai":    return openai_call(prompt, system_prompt)
    if provider == "gemini":    return gemini_call(prompt, system_prompt)
    if provider == "groq":      return groq_call(prompt, system_prompt)
    if provider == "openrouter":return openrouter_call(prompt, system_prompt)
    if provider == "deepseek":  return deepseek_call(prompt, system_prompt)
    if provider == "nvidia":    return nvidia_call(prompt, system_prompt)
    if provider == "anthropic": return anthropic_call(prompt, system_prompt)
    return f"Unknown provider: {provider}"
