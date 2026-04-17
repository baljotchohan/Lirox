"""Lirox v2.0.0 — Multi-Provider LLM Layer

Supports: Groq, Gemini, OpenAI, Anthropic, OpenRouter, Ollama
Auto-fallback to next available provider on error.
Use /use-model to pin a specific provider.
"""
from __future__ import annotations

import os
import time
import requests
from typing import Optional, List

_LLM_TIMEOUT = 90

DEFAULT_SYSTEM = (
    "You are Lirox, an autonomous personal AI agent. Be direct, precise, and complete. "
    "When writing code — write the COMPLETE implementation. Never truncate. "
    "Never use '...' or placeholders. Always include all imports. "
    "When asked to do something — DO IT. Do not describe how to do it."
)

_PROVIDER_ENV_MAP = {
    "groq":       "GROQ_API_KEY",
    "gemini":     "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai":     "OPENAI_API_KEY",
    "anthropic":  "ANTHROPIC_API_KEY",
}
_PROVIDER_PRIORITY = ["groq", "openrouter", "gemini", "anthropic", "openai"]


def strip_code_fences(text: str, lang: str = "") -> str:
    """Strip markdown code fences from LLM output."""
    text = text.strip()
    for fence in (f"```{lang}", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            break
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def openai_call(prompt: str, system_prompt: Optional[str] = None,
                model: str = "gpt-4o") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OpenAI API key missing."
    try:
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenAI Error: {e}"


def gemini_call(prompt: str, system_prompt: Optional[str] = None) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini API key missing."
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt or DEFAULT_SYSTEM, temperature=0.7)
        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                return client.models.generate_content(
                    model=model_name, contents=prompt, config=config).text
            except Exception:
                continue
        return "Gemini Error: All models failed"
    except ImportError:
        return "google-genai not installed. Run: pip install google-genai"
    except Exception as e:
        return f"Gemini Error: {e}"


def groq_call(prompt: str, system_prompt: Optional[str] = None,
              model: str = "llama-3.3-70b-versatile") -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Groq API key missing."
    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Groq Error: {e}"


def openrouter_call(prompt: str, system_prompt: Optional[str] = None,
                    model: str = "mistralai/mistral-7b-instruct:free") -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "OpenRouter API key missing."
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json",
                     "HTTP-Referer": "https://lirox.ai",
                     "X-Title": "Lirox Agent OS"},
            json={"model": model, "messages": [
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM},
                {"role": "user",   "content": prompt}]},
            timeout=_LLM_TIMEOUT)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenRouter Error: {e}"


def anthropic_call(prompt: str, system_prompt: Optional[str] = None,
                   model: str = "claude-3-5-haiku-20241022") -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
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
    except Exception as e:
        return f"Anthropic Error: {e}"


def ollama_call(prompt: str, system_prompt: Optional[str] = None,
                model: str = None) -> str:
    endpoint    = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    model       = model or os.getenv("OLLAMA_MODEL", "llama3")
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        res = requests.post(
            f"{endpoint}/api/generate",
            json={"model": model, "prompt": full_prompt, "stream": False},
            timeout=120)
        res.raise_for_status()
        return res.json().get("response", "Ollama Error: empty response")
    except requests.exceptions.ConnectionError:
        return "Ollama Error: server not running. Start with: ollama serve"
    except Exception as e:
        return f"Ollama Error: {e}"


def _is_ollama_available() -> bool:
    try:
        res = requests.get(
            f"{os.getenv('OLLAMA_ENDPOINT', 'http://localhost:11434')}/api/tags",
            timeout=2)
        return res.status_code == 200
    except Exception:
        return False


def available_providers() -> List[str]:
    providers = [n for n, k in _PROVIDER_ENV_MAP.items() if os.getenv(k)]
    if os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true":
        if _is_ollama_available():
            providers.insert(0, "ollama")
    return providers


def pick_default_provider() -> Optional[str]:
    avail = available_providers()
    for p in _PROVIDER_PRIORITY:
        if p in avail:
            return p
    if "ollama" in avail:
        return "ollama"
    return None


def is_error_response(text: str) -> bool:
    if not text or len(text.strip()) < 5:
        return True
    lowered = text.strip().lower()
    if any(s in lowered for s in ["api key missing", "api key not set"]):
        return True
    error_prefixes = [
        "openai error:", "gemini error:", "groq error:", "anthropic error:",
        "openrouter error:", "ollama error:", "error:", "unknown provider:",
        "rate limit exceeded",
    ]
    return any(lowered.startswith(p) for p in error_prefixes)


def generate_response(prompt: str, provider: str = "auto",
                      system_prompt: str = None,
                      timeout: Optional[int] = None) -> str:
    if timeout is None:
        from lirox.config import LLM_TIMEOUT
        timeout = LLM_TIMEOUT

    # Honour /use-model pin
    _pinned = os.getenv("_LIROX_PINNED_MODEL", "")
    if _pinned and _pinned != "auto" and provider == "auto":
        provider = _pinned

    if provider == "auto":
        if os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true":
            if _is_ollama_available():
                resp = ollama_call(prompt, system_prompt)
                if not is_error_response(resp):
                    return resp
        provider = pick_default_provider()

    if provider is None:
        return (
            "No API keys configured. Run /setup to add one.\n"
            "Free options: Groq (groq.com) · Gemini (aistudio.google.com) · Ollama (local)"
        )

    provider = provider.lower().strip("[]'\" ")

    if provider == "ollama":
        if not _is_ollama_available():
            fb = pick_default_provider()
            if not fb:
                return "Ollama not running and no cloud keys configured."
            provider = fb
    elif provider not in ("ollama",) and not os.getenv(_PROVIDER_ENV_MAP.get(provider, "")):
        fb = pick_default_provider()
        if not fb:
            return "No API keys configured. Run /setup."
        provider = fb

    response = _call_provider(provider, prompt, system_prompt)

    if is_error_response(response):
        avail = available_providers()
        for fb in [p for p in _PROVIDER_PRIORITY if p in avail and p != provider]:
            try:
                time.sleep(1)
                retry = _call_provider(fb, prompt, system_prompt)
                if not is_error_response(retry):
                    return retry
            except Exception:
                continue

    return response or "Error: All providers failed."


def _call_provider(provider: str, prompt: str, system_prompt: Optional[str]) -> str:
    dispatch = {
        "openai":     openai_call,
        "gemini":     gemini_call,
        "groq":       groq_call,
        "openrouter": openrouter_call,
        "anthropic":  anthropic_call,
        "ollama":     ollama_call,
    }
    fn = dispatch.get(provider)
    if fn is None:
        return f"Unknown provider: {provider}"
    return fn(prompt, system_prompt)
