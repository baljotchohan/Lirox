"""Lirox v1.1 — LLM Utility Layer"""
import logging
import os
import hashlib
import time
import threading
import requests
import concurrent.futures
from collections import OrderedDict
from typing import List, Dict, Optional, Generator

from lirox.utils.managed_pool import get_default_pool as _get_pool

_logger = logging.getLogger("lirox.llm")

_OLLAMA_OPTIONS = {
    "num_ctx": 8192, "num_thread": 4, "num_batch": 512,
    "num_predict": 2048, "num_keep": 64, "repeat_last_n": 64,
}


def _get_api_key(provider: str) -> Optional[str]:
    """Return the API key for *provider*, with format validation.

    SECURITY-01 fix: centralises all key access through secure_keys so that
    key presence is audit-logged (via secure_keys.get_api_key) and basic
    format checks are applied before use.  A warning is emitted if the key
    does not match the expected format for the provider.
    """
    from lirox.utils.secure_keys import get_api_key, validate_key_format
    key = get_api_key(provider)
    if key:
        valid, reason = validate_key_format(provider, key)
        if not valid:
            _logger.warning("API key for '%s' may be invalid: %s", provider, reason)
    return key

DEFAULT_SYSTEM = (
    "You are Lirox, a premium autonomous AI agent. Be direct, precise, and complete. "
    "CRITICAL: When writing code — write the COMPLETE implementation. Never truncate. "
    "Never use '...' or placeholders. Always include all imports and a usage example. "
    "CRITICAL: You have full filesystem access. Never say you cannot access the filesystem. "
    "CRITICAL: When asked to do something — DO IT. Do not describe how to do it."
)

_LLM_TIMEOUT  = 90

class _LRUCache(OrderedDict):
    """Simple LRU cache with max size (FIX-17)."""
    def __init__(self, maxsize=256):
        super().__init__()
        self._maxsize = maxsize
    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self._maxsize:
            self.popitem(last=False)

_task_cache = _LRUCache(256)


def strip_code_fences(text: str, lang: str = "") -> str:
    """
    Safely strip markdown code fences from LLM output.
    Unlike lstrip/rstrip, this removes the literal fence strings,
    not individual characters.
    """
    text = text.strip()
    # Remove opening fence (```python, ```json, or plain ```)
    for fence in (f"```{lang}", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            break
    # Remove closing fence
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _hash_prompt(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()[:16]


def openai_call(prompt: str, system_prompt: Optional[str] = None, model: str = "gpt-4o") -> str:
    api_key = _get_api_key("openai")
    if not api_key:
        return "OpenAI API key missing."
    try:
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        try:
            return f"OpenAI Error: {e.response.json().get('error', {}).get('message', str(e))}"
        except Exception:
            return f"OpenAI Error: {e}"
    except Exception as e:
        return f"OpenAI Error: {e}"


def gemini_call(prompt: str, system_prompt: Optional[str] = None) -> str:
    api_key = _get_api_key("gemini")
    if not api_key:
        return "Gemini API key missing."
    try:
        from google import genai
        from google.genai import types
        client   = genai.Client(api_key=api_key)
        config   = types.GenerateContentConfig(
            system_instruction=system_prompt or DEFAULT_SYSTEM, temperature=0.7)
        last_error = None
        for model_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                return client.models.generate_content(
                    model=model_name, contents=prompt, config=config).text
            except Exception as e:
                last_error = e
                continue
        return f"Gemini Error: All models failed. Last error: {last_error}"
    except ImportError:
        return "google-genai not installed. Run: pip install google-genai"
    except Exception as e:
        return f"Gemini Error: {e}"


def groq_call(prompt: str, system_prompt: Optional[str] = None,
              model: str = "llama-3.3-70b-versatile") -> str:
    api_key = _get_api_key("groq")
    if not api_key:
        return "Groq API key missing."
    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        try:
            return f"Groq Error: {e.response.json().get('error', {}).get('message', str(e))}"
        except Exception:
            return f"Groq Error: {e}"
    except Exception as e:
        return f"Groq Error: {e}"


def openrouter_call(prompt: str, system_prompt: Optional[str] = None,
                    model: str = "mistralai/mistral-7b-instruct:free") -> str:
    api_key = _get_api_key("openrouter")
    if not api_key:
        return "OpenRouter API key missing."
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://lirox.ai", "X-Title": "Lirox Agent OS"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        try:
            return f"OpenRouter Error: {e.response.json().get('error', {}).get('message', str(e))}"
        except Exception:
            return f"OpenRouter Error: {e}"
    except Exception as e:
        return f"OpenRouter Error: {e}"


def deepseek_call(prompt: str, system_prompt: Optional[str] = None,
                  model: str = "deepseek-chat") -> str:
    api_key = _get_api_key("deepseek")
    if not api_key:
        return "DeepSeek API key missing."
    try:
        res = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        try:
            return f"DeepSeek Error: {e.response.json().get('error', {}).get('message', str(e))}"
        except Exception:
            return f"DeepSeek Error: {e}"
    except Exception as e:
        return f"DeepSeek Error: {e}"


def nvidia_call(prompt: str, system_prompt: Optional[str] = None,
                model: str = "meta/llama-3.1-405b-instruct") -> str:
    api_key = _get_api_key("nvidia")
    if not api_key:
        return "NVIDIA API key missing."
    try:
        res = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        try:
            return f"NVIDIA Error: {e.response.json().get('error', {}).get('message', str(e))}"
        except Exception:
            return f"NVIDIA Error: {e}"
    except Exception as e:
        return f"NVIDIA Error: {e}"


def ollama_call(prompt: str, system_prompt: Optional[str] = None, model: str = None) -> str:
    import gc
    endpoint    = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    model       = model or os.getenv("OLLAMA_MODEL", "llama3")
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        res = requests.post(
            f"{endpoint}/api/generate",
            json={"model": model, "prompt": full_prompt, "stream": False,
                  "options": _OLLAMA_OPTIONS},
            timeout=120)
        res.raise_for_status()
        return res.json().get("response", "Ollama Error: empty response")
    except requests.exceptions.ConnectionError:
        return "Ollama Error: server not running. Start with: ollama serve"
    except requests.exceptions.HTTPError as e:
        try:
            return f"Ollama Error: {e.response.json().get('error', str(e))}"
        except Exception:
            return f"Ollama Error: {e}"
    except Exception as e:
        return f"Ollama Error: {e}"
    finally:
        gc.collect()


def hf_bnb_call(prompt: str, system_prompt: Optional[str] = None, model: str = None) -> str:
    import gc
    endpoint    = os.getenv("HF_BNB_ENDPOINT", "http://localhost:11435")
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        res = requests.post(
            f"{endpoint}/api/generate",
            json={"prompt": full_prompt, "options": _OLLAMA_OPTIONS},
            timeout=120)
        res.raise_for_status()
        return res.json().get("response", "HF BNB Error: empty response")
    except requests.exceptions.ConnectionError:
        return "HF BNB Error: server not running."
    except Exception as e:
        return f"HF BNB Error: {e}"
    finally:
        gc.collect()


def anthropic_call(prompt: str, system_prompt: Optional[str] = None,
                   model: str = "claude-3-5-haiku-20241022") -> str:
    api_key = _get_api_key("anthropic")
    if not api_key:
        return "Anthropic API key missing."
    try:
        import anthropic
        client  = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model, max_tokens=4096,
            system=system_prompt or DEFAULT_SYSTEM,
            messages=[{"role": "user", "content": prompt}])
        return message.content[0].text
    except ImportError:
        pass
    except Exception as e:
        return f"Anthropic SDK Error: {e}"
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": model, "max_tokens": 4096,
                  "system": system_prompt or DEFAULT_SYSTEM,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["content"][0]["text"]
    except requests.exceptions.HTTPError as e:
        try:
            return f"Anthropic Error: {e.response.json().get('error', {}).get('message', str(e))}"
        except Exception:
            return f"Anthropic Error: {e}"
    except Exception as e:
        return f"Anthropic Error: {e}"


_PROVIDER_ENV_MAP = {
    "gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY", "nvidia": "NVIDIA_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
_PROVIDER_PRIORITY = ["groq", "openrouter", "gemini", "anthropic", "nvidia", "openai", "deepseek"]

TASK_KEYWORDS = [
    "create", "build", "run", "install", "download", "execute", "pip", "npm",
    "search", "lookup", "research", "set up", "write a script", "generate",
    "make a folder", "mkdir", "open", "launch", "deploy", "find", "analyze",
    "write code", "fix code", "debug",
]
RESEARCH_KEYWORDS = [
    "who is", "what is", "explain", "how does", "why does",
    "tell me about", "research", "find out", "what are", "compare",
]


_ollama_cache_ts = 0.0
_ollama_cache_val = False
_ollama_cache_lock = threading.Lock()
_OLLAMA_CACHE_TTL = 10  # seconds


def _is_ollama_available() -> bool:
    """Check Ollama availability with 10s cache (FIX-16, thread-safe)."""
    global _ollama_cache_ts, _ollama_cache_val
    import time as _t
    now = _t.time()
    with _ollama_cache_lock:
        if now - _ollama_cache_ts < _OLLAMA_CACHE_TTL:
            return _ollama_cache_val
    try:
        res = requests.get(
            f"{os.getenv('OLLAMA_ENDPOINT', 'http://localhost:11434')}/api/tags", timeout=2)
        result = res.status_code == 200
    except Exception:
        result = False
    with _ollama_cache_lock:
        _ollama_cache_val = result
        _ollama_cache_ts = _t.time()
    return result


def _is_hf_bnb_available() -> bool:
    import socket
    from urllib.parse import urlparse
    endpoint = os.getenv("HF_BNB_ENDPOINT", "http://127.0.0.1:11435")
    try:
        parsed = urlparse(endpoint)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11435
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False


def available_providers() -> List[str]:
    providers = [n for n, k in _PROVIDER_ENV_MAP.items() if os.getenv(k)]
    if os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true":
        local = os.getenv("LOCAL_LLM_PROVIDER", "ollama").lower()
        if local == "ollama" and _is_ollama_available():
            providers.insert(0, "ollama")
        elif local == "hf_bnb" and _is_hf_bnb_available():
            providers.insert(0, "hf_bnb")
    return providers


def provider_has_key(provider: str) -> bool:
    return provider.lower() in available_providers()


def pick_default_provider() -> Optional[str]:
    avail = available_providers()
    for p in _PROVIDER_PRIORITY:
        if p in avail:
            return p
    return None


def smart_router(prompt: str) -> Optional[str]:
    avail   = available_providers()
    lowered = prompt.lower()
    if any(k in lowered for k in ["complex", "reason", "analyze"]) and "anthropic" in avail:
        return "anthropic"
    if any(k in lowered for k in ["code", "script", "debug", "function"]) and "groq" in avail:
        return "groq"
    if any(k in lowered for k in RESEARCH_KEYWORDS) and "openrouter" in avail:
        return "openrouter"
    return pick_default_provider()


def is_error_response(text: str) -> bool:
    if not text or len(text.strip()) < 5:
        return True
    lowered = text.strip().lower()
    # FIX-12: Catch ALL provider error formats including install messages
    error_indicators = [
        "api key missing", "api key not set", "not installed",
        "error:", "rate limit exceeded",
    ]
    if any(s in lowered for s in error_indicators):
        return True
    error_prefixes = [
        "openai error", "gemini error", "groq error", "anthropic error", "anthropic sdk error",
        "deepseek error", "nvidia error", "openrouter error", "ollama error",
        "hf bnb error", "unknown provider",
    ]
    return any(lowered.startswith(p) for p in error_prefixes)


def is_task_request(user_input: str, provider: str = "auto") -> bool:
    lowered = user_input.lower()
    if any(k in lowered for k in TASK_KEYWORDS):
        return True
    if any(lowered.startswith(s) for s in ["who ", "what ", "why ", "when ", "how ",
                                             "is ", "are ", "do ", "does "]) \
            and len(user_input.split()) < 15:
        return False
    cache_key = _hash_prompt(user_input)
    if cache_key in _task_cache:
        return _task_cache[cache_key]
    result = any(k in lowered for k in ["build", "create", "fix", "write", "debug"])
    _task_cache[cache_key] = result   # FIX: write result to cache
    return result


def generate_response(prompt: str, provider: str = "auto",
                      system_prompt: str = None,
                      timeout: Optional[int] = None) -> str:
    if timeout is None:
        from lirox.config import LLM_TIMEOUT
        timeout = LLM_TIMEOUT

    # Honour /use-model pin — overrides caller's provider unless caller was explicit
    _pinned = os.getenv("_LIROX_PINNED_MODEL", "")
    if _pinned and _pinned != "auto" and provider == "auto":
        provider = _pinned

    if provider == "auto":
        if os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true":
            local   = os.getenv("LOCAL_LLM_PROVIDER", "ollama").lower()
            checker = _is_ollama_available if local == "ollama" else _is_hf_bnb_available
            if checker():
                try:
                    future = _get_pool().submit(_call_provider, local, prompt, system_prompt)
                    resp   = future.result(timeout=timeout)
                    if not is_error_response(resp):
                        return resp
                except Exception:
                    pass
        provider = smart_router(prompt)

    if provider is None:
        return (
            "No API keys configured. Run /setup to add one.\n"
            "Free: Groq (groq.com) · Gemini (aistudio.google.com) · Ollama (local)"
        )

    provider = provider.lower().strip("[]'\" ")

    if provider == "ollama" and not _is_ollama_available():
        fb = pick_default_provider()
        if not fb:
            return "Ollama not running (ollama serve) and no cloud keys configured."
        provider = fb
    elif provider not in ("ollama", "hf_bnb") and not provider_has_key(provider):
        fb = pick_default_provider()
        if not fb:
            return "No API keys configured. Run /setup."
        provider = fb

    response = None
    try:
        future   = _get_pool().submit(_call_provider, provider, prompt, system_prompt)
        response = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return f"Error: LLM API timed out after {timeout}s"
    except (SystemExit, KeyboardInterrupt):
        raise
    except ValueError as e:
        response = f"Error: Invalid request — {e}"
    except RuntimeError as e:
        # ISSUE-12 fix: explicit handler for RuntimeError (e.g. thread-pool shutdown)
        _logger.error("Runtime error in LLM dispatch: %s", e)
        response = f"Error: Runtime failure — {e}"
    except AttributeError as e:
        # ISSUE-12 fix: explicit handler for AttributeError (e.g. uninitialised provider)
        _logger.error("Attribute error in LLM dispatch: %s", e)
        response = f"Error: Internal error — {e}"
    except requests.RequestException as e:
        response = f"Error: Network failure — {e}"
    except Exception as e:
        _logger.exception("Unexpected error in generate_response")
        response = f"Error: {e}"

    if response is None or is_error_response(response):
        avail = available_providers()
        # BUG-06 FIX: only increment `attempt` when we actually call a provider,
        # not when we skip it due to rate limiting, so backoff is not wasted.
        attempt = 0
        for fb in [p for p in _PROVIDER_PRIORITY if p in avail and p != provider]:
            try:
                if attempt > 0:
                    time.sleep(2 ** (attempt - 1))  # exponential backoff: 1s, 2s, 4s…
                from lirox.utils.rate_limiter import api_limiter
                if not api_limiter.is_allowed(fb):
                    continue  # skip rate-limited provider WITHOUT incrementing attempt
                future = _get_pool().submit(_call_provider, fb, prompt, system_prompt)
                retry = future.result(timeout=timeout)
                attempt += 1  # increment only after an actual call attempt
                if not is_error_response(retry):
                    return retry
            except (SystemExit, KeyboardInterrupt):
                raise
            except Exception:
                attempt += 1
                continue

    return response or "Error: All providers failed."


def _call_provider(provider: str, prompt: str, system_prompt: Optional[str]) -> str:
    from lirox.utils.rate_limiter import api_limiter, sys_monitor
    if not api_limiter.is_allowed(provider):
        return f"Rate limit exceeded: {provider}"
    for _ in range(3):
        if sys_monitor.check_resources():
            break
        time.sleep(2)
    api_limiter.record_call(provider)
    dispatch = {
        "openai": openai_call, "gemini": gemini_call, "groq": groq_call,
        "openrouter": openrouter_call, "deepseek": deepseek_call,
        "nvidia": nvidia_call, "anthropic": anthropic_call,
        "ollama": ollama_call, "hf_bnb": hf_bnb_call,
    }
    fn = dispatch.get(provider)
    return fn(prompt, system_prompt) if fn else f"Unknown provider: {provider}"
