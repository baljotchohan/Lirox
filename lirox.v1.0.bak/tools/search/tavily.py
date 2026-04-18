"""Tavily Search — paid API (optional)."""
import os


def search_tavily(query: str, max_results: int = 5) -> str:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return ""
    try:
        import requests

        resp = requests.post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": max_results, "api_key": key},
            timeout=15,
        )
        resp.raise_for_status()
        return "\n".join(
            f"- {r.get('title', '')}: {r.get('content', '')[:200]}\n  {r.get('url', '')}"
            for r in resp.json().get("results", [])
        )
    except Exception as e:
        return f"Tavily error: {e}"
