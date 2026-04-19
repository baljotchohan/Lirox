"""Lirox v1.1 — Configuration Validator

Root-cause fix: validates the runtime configuration before any LLM calls
are made so that misconfigured environments fail fast with a clear error
instead of propagating confusing downstream failures.

Usage
-----
    from lirox.core.config_validator import validate_config, ConfigReport

    report = validate_config()
    if not report.is_valid:
        for issue in report.errors:
            print(f"[ERROR] {issue}")
    for warn in report.warnings:
        print(f"[WARN]  {warn}")
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Timeout range constants
# ---------------------------------------------------------------------------

MIN_LLM_TIMEOUT: int = 10    # seconds — below this, most LLMs will always time out
MAX_LLM_TIMEOUT: int = 300   # seconds — above this, UX degrades significantly

MIN_SHELL_TIMEOUT: int = 5   # seconds — very short commands still need a few seconds
MAX_SHELL_TIMEOUT: int = 300

MIN_FILE_TIMEOUT: int = 5
MAX_FILE_TIMEOUT: int = 120


@dataclass
class ConfigReport:
    """Result of a configuration validation pass."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when there are no errors (warnings are acceptable)."""
        return len(self.errors) == 0

    def __str__(self) -> str:
        lines: List[str] = []
        for e in self.errors:
            lines.append(f"[ERROR]   {e}")
        for w in self.warnings:
            lines.append(f"[WARNING] {w}")
        for i in self.info:
            lines.append(f"[INFO]    {i}")
        return "\n".join(lines) if lines else "Configuration OK"


def validate_config(strict: bool = False) -> ConfigReport:
    """Validate the Lirox runtime configuration.

    Parameters
    ----------
    strict : bool
        When True, treat warnings as errors.

    Returns
    -------
    ConfigReport
        Structured result with any errors, warnings, and informational items.
    """
    report = ConfigReport()
    _check_python_version(report)
    _check_api_keys(report)
    _check_timeouts(report)
    _check_memory_limits(report)
    _check_paths(report)
    _check_local_llm(report)

    if strict:
        report.errors.extend(report.warnings)
        report.warnings.clear()

    return report


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------

def _check_python_version(report: ConfigReport) -> None:
    import sys
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 9):
        report.errors.append(
            f"Python >=3.9 required; running {major}.{minor}."
        )
    else:
        report.info.append(f"Python {major}.{minor} — OK")


def _check_api_keys(report: ConfigReport) -> None:
    """Warn if no API keys are configured (not an error — local LLM may be used)."""
    key_envs = [
        "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
        "NVIDIA_API_KEY",
    ]
    configured = [k for k in key_envs if os.getenv(k)]
    local_enabled = os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true"

    if not configured and not local_enabled:
        report.warnings.append(
            "No LLM API keys found and LOCAL_LLM_ENABLED is not set. "
            "Run /setup to add a provider key or set LOCAL_LLM_ENABLED=true."
        )
    else:
        report.info.append(
            f"Providers with API keys: {', '.join(k.replace('_API_KEY', '').lower() for k in configured) or 'none (local only)'}"
        )


def _check_timeouts(report: ConfigReport) -> None:
    """Validate that configured timeouts are in sane ranges."""
    checks = [
        ("LIROX_LLM_TIMEOUT",   "LLM_TIMEOUT",   MIN_LLM_TIMEOUT,   MAX_LLM_TIMEOUT,   "LLM timeout"),
        ("LIROX_SHELL_TIMEOUT",  "SHELL_TIMEOUT",  MIN_SHELL_TIMEOUT, MAX_SHELL_TIMEOUT, "shell timeout"),
        ("LIROX_FILE_TIMEOUT",   None,             MIN_FILE_TIMEOUT,  MAX_FILE_TIMEOUT,  "file timeout"),
    ]
    for primary, fallback, lo, hi, label in checks:
        raw = os.getenv(primary) or (os.getenv(fallback) if fallback else None)
        if raw is None:
            continue
        try:
            val = int(raw)
        except ValueError:
            report.errors.append(
                f"{primary} must be an integer, got '{raw}'."
            )
            continue
        if val < lo:
            report.warnings.append(
                f"{label} ({val}s) is very low — minimum recommended is {lo}s."
            )
        elif val > hi:
            report.warnings.append(
                f"{label} ({val}s) is very high — maximum recommended is {hi}s."
            )


def _check_memory_limits(report: ConfigReport) -> None:
    raw = os.getenv("MEMORY_LIMIT")
    if raw is None:
        return
    try:
        val = int(raw)
    except ValueError:
        report.errors.append(f"MEMORY_LIMIT must be an integer, got '{raw}'.")
        return
    if val < 10:
        report.warnings.append(
            f"MEMORY_LIMIT={val} is very small — context may be lost quickly."
        )
    elif val > 10_000:
        report.warnings.append(
            f"MEMORY_LIMIT={val} is very large — memory usage may be high."
        )


def _check_paths(report: ConfigReport) -> None:
    """Check that LIROX_WORKSPACE exists or can be created."""
    workspace = os.getenv("LIROX_WORKSPACE", "")
    if not workspace:
        return
    import pathlib
    try:
        p = pathlib.Path(workspace).expanduser().resolve()
        if not p.exists():
            report.warnings.append(
                f"LIROX_WORKSPACE '{workspace}' does not exist — it will be created on first use."
            )
    except (OSError, RuntimeError) as exc:
        report.errors.append(f"LIROX_WORKSPACE path error: {exc}")


def _check_local_llm(report: ConfigReport) -> None:
    """If local LLM is enabled, check the endpoint is configured."""
    if os.getenv("LOCAL_LLM_ENABLED", "false").lower() != "true":
        return
    provider = os.getenv("LOCAL_LLM_PROVIDER", "ollama").lower()
    if provider == "ollama":
        endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
        report.info.append(f"Local LLM: Ollama at {endpoint}")
    elif provider == "hf_bnb":
        endpoint = os.getenv("HF_BNB_ENDPOINT", "http://127.0.0.1:11435")
        report.info.append(f"Local LLM: HF BNB at {endpoint}")
    else:
        report.warnings.append(
            f"LOCAL_LLM_PROVIDER='{provider}' is not recognised (expected 'ollama' or 'hf_bnb')."
        )
