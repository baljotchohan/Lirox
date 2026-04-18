"""Lirox v3.0 — Secure API Key Management

Provides a manager that:
- Validates API keys are present before use
- Masks keys in any string representations (no key leakage in logs)
- Keeps an audit log of which keys were accessed (without logging values)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

_logger = logging.getLogger("lirox.secure_keys")

# Map of provider name -> environment variable name
_KEY_ENV_MAP: dict[str, str] = {
    "openai":      "OPENAI_API_KEY",
    "gemini":      "GEMINI_API_KEY",
    "openrouter":  "OPENROUTER_API_KEY",
    "groq":        "GROQ_API_KEY",
    "deepseek":    "DEEPSEEK_API_KEY",
    "nvidia":      "NVIDIA_API_KEY",
    "anthropic":   "ANTHROPIC_API_KEY",
    "tavily":      "TAVILY_API_KEY",
}


def _mask(key: str) -> str:
    """Return a masked representation suitable for logging."""
    if not key:
        return "<not set>"
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def get_api_key(provider: str) -> Optional[str]:
    """Return the API key for *provider*, or None if not configured.

    Audit-logs the access (without the key value).
    """
    env_var = _KEY_ENV_MAP.get(provider.lower())
    if not env_var:
        _logger.warning("get_api_key: unknown provider '%s'", provider)
        return None
    value = os.getenv(env_var)
    if value:
        _logger.debug("API key accessed for provider '%s' (%s)", provider, _mask(value))
    else:
        _logger.debug("API key not configured for provider '%s'", provider)
    return value or None


def has_api_key(provider: str) -> bool:
    """Return True if an API key is configured for *provider*."""
    return bool(get_api_key(provider))


def configured_providers() -> list[str]:
    """Return a list of providers for which an API key is available."""
    return [p for p in _KEY_ENV_MAP if has_api_key(p)]


def validate_key_format(provider: str, key: str) -> tuple[bool, str]:
    """Basic structural validation of a key (length, prefix checks).

    Returns (valid: bool, reason: str).
    """
    if not key or not key.strip():
        return False, "Key is empty"
    key = key.strip()
    min_lengths = {
        "openai":     40,
        "groq":       40,
        "anthropic":  40,
        "gemini":     30,
        "openrouter": 30,
        "deepseek":   30,
        "nvidia":     30,
        "tavily":     20,
    }
    expected_prefixes = {
        "openai":    ("sk-",),
        "anthropic": ("sk-ant-",),
    }
    min_len = min_lengths.get(provider.lower(), 20)
    if len(key) < min_len:
        return False, f"Key too short (expected ≥{min_len} chars)"
    prefixes = expected_prefixes.get(provider.lower())
    if prefixes and not any(key.startswith(p) for p in prefixes):
        return False, f"Unexpected key prefix for {provider}"
    return True, "ok"
