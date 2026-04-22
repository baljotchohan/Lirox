from unittest.mock import patch

from lirox.llm.providers import LLMRequest, LLMRouter


def test_recommend_prefers_coding_provider():
    router = LLMRouter()
    with patch("lirox.utils.llm.available_providers", return_value=["openai", "groq"]):
        assert router.recommend(task_type="coding") == "groq"


def test_call_uses_fallback_chain():
    router = LLMRouter()
    calls = []

    def _fake(prompt, provider, system_prompt=None):
        calls.append(provider)
        if provider == "groq":
            raise RuntimeError("provider down")
        return "ok response"

    with patch("lirox.utils.llm.available_providers", return_value=["groq", "openai"]):
        with patch("lirox.utils.llm.generate_response", side_effect=_fake):
            resp = router.call(LLMRequest(prompt="hello", task_type="coding"))

    assert resp.ok
    assert resp.text == "ok response"
    assert calls[:2] == ["groq", "openai"]

