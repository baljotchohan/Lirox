"""Enterprise-style provider routing on top of existing Lirox provider clients."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

from lirox.core.errors import ProviderError


@dataclass
class LLMRequest:
    prompt: str
    system_prompt: Optional[str] = None
    task_type: str = "general"          # coding | reasoning | research | general
    provider: str = "auto"
    preferred: Optional[str] = None
    max_fallbacks: int = 4


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str = ""
    ok: bool = True
    error: str = ""
    attempts: List[Dict[str, Any]] = field(default_factory=list)


class LLMRouter:
    """Provider abstraction with routing and fallback chains."""

    _TASK_PRIORITIES: Dict[str, List[str]] = {
        "coding": ["groq", "anthropic", "deepseek", "openai", "openrouter", "gemini", "ollama"],
        "reasoning": ["anthropic", "openai", "gemini", "openrouter", "groq", "deepseek", "ollama"],
        "research": ["openrouter", "gemini", "openai", "anthropic", "groq", "deepseek", "ollama"],
        "general": ["groq", "openrouter", "gemini", "openai", "anthropic", "deepseek", "ollama"],
    }

    def available(self) -> List[str]:
        from lirox.utils.llm import available_providers
        return available_providers()

    def health(self) -> Dict[str, Dict[str, Any]]:
        from lirox.utils.llm import provider_has_key
        available = set(self.available())
        providers = ["groq", "openai", "gemini", "openrouter", "anthropic", "deepseek", "ollama"]
        out: Dict[str, Dict[str, Any]] = {}
        for p in providers:
            if p == "ollama":
                ok = p in available
                out[p] = {"ok": ok, "available": ok}
            else:
                out[p] = {"ok": provider_has_key(p), "available": p in available}
        return out

    def recommend(self, task_type: str = "general", preferred: Optional[str] = None) -> str:
        avail = self.available()
        if preferred and preferred in avail:
            return preferred
        t = task_type.lower().strip()
        order = self._TASK_PRIORITIES.get(t, self._TASK_PRIORITIES["general"])
        for p in order:
            if p in avail:
                return p
        return avail[0] if avail else "groq"

    def fallback_chain(
        self,
        task_type: str = "general",
        provider: str = "auto",
        preferred: Optional[str] = None,
        max_fallbacks: int = 4,
    ) -> List[str]:
        avail = self.available()
        if provider and provider != "auto":
            return [provider] + [p for p in avail if p != provider][:max_fallbacks]
        primary = self.recommend(task_type=task_type, preferred=preferred)
        ordered = [primary] + [p for p in avail if p != primary]
        return ordered[: max_fallbacks + 1]

    def call(self, req: LLMRequest) -> LLMResponse:
        from lirox.utils.llm import generate_response

        chain = self.fallback_chain(
            task_type=req.task_type,
            provider=req.provider,
            preferred=req.preferred,
            max_fallbacks=req.max_fallbacks,
        )
        attempts: List[Dict[str, Any]] = []
        last_error = "No providers available"

        for provider in chain:
            try:
                text = generate_response(
                    req.prompt,
                    provider=provider,
                    system_prompt=req.system_prompt,
                )
                if isinstance(text, str) and text.strip():
                    attempts.append({"provider": provider, "ok": True})
                    return LLMResponse(
                        text=text,
                        provider=provider,
                        ok=True,
                        attempts=attempts,
                    )
                last_error = "Empty response"
                attempts.append({"provider": provider, "ok": False, "error": last_error})
            except Exception as exc:
                last_error = str(exc)
                attempts.append({"provider": provider, "ok": False, "error": last_error})

        return LLMResponse(
            text="",
            provider=chain[-1] if chain else "",
            ok=False,
            error=last_error,
            attempts=attempts,
        )

    def stream(self, req: LLMRequest, chunk_size: int = 180) -> Generator[str, None, None]:
        """Streaming compatibility contract using chunked fallback output."""
        resp = self.call(req)
        if not resp.ok:
            raise ProviderError(resp.provider or "unknown", resp.error or "LLM call failed", retryable=True)
        txt = resp.text
        for i in range(0, len(txt), chunk_size):
            yield txt[i:i + chunk_size]


def llm_call(
    prompt: str,
    *,
    task_type: str = "general",
    provider: str = "auto",
    system_prompt: Optional[str] = None,
    preferred: Optional[str] = None,
) -> str:
    router = LLMRouter()
    resp = router.call(
        LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            task_type=task_type,
            provider=provider,
            preferred=preferred,
        )
    )
    if not resp.ok:
        raise ProviderError(resp.provider or "unknown", resp.error or "LLM call failed", retryable=True)
    return resp.text


def llm_stream(
    prompt: str,
    *,
    task_type: str = "general",
    provider: str = "auto",
    system_prompt: Optional[str] = None,
    preferred: Optional[str] = None,
) -> Generator[str, None, None]:
    router = LLMRouter()
    req = LLMRequest(
        prompt=prompt,
        system_prompt=system_prompt,
        task_type=task_type,
        provider=provider,
        preferred=preferred,
    )
    yield from router.stream(req)

