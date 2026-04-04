"""Self-evaluation for result quality assessment."""
import json
from lirox.utils.llm import generate_response
from lirox.config import MAX_TOOL_RESULT_CHARS


def evaluate_result(query: str, result: str, provider: str = "auto") -> dict:
    try:
        resp = generate_response(
            f'Rate 1-10. Return JSON: {{"score":N,"complete":bool,"missing":"..."}}\nQuery: {query}\nResult: {result[:MAX_TOOL_RESULT_CHARS]}',
            provider,
            system_prompt="Return ONLY valid JSON.",
        )
        cleaned = resp.strip().strip("`").replace("```json", "").replace("```", "")
        return json.loads(cleaned)
    except Exception:
        return {"score": 5, "complete": True, "missing": ""}
