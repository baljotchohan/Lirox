"""Lirox v2.0.0 — Search Tools

Provides web search (DuckDuckGo) and page fetching.
"""
from __future__ import annotations

import os
from typing import List, Optional


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo.
    Returns formatted results as a string.
    """
    if not query or not query.strip():
        return "Error: Empty search query."

    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title   = r.get("title", "")
                url     = r.get("href", "")
                snippet = r.get("body", "")
                results.append(f"**{title}**\n{url}\n{snippet}")
        if not results:
            return "No search results found."
        return "\n\n".join(results[:max_results])
    except ImportError:
        return (
            "duckduckgo-search not installed. "
            "Run: pip install duckduckgo-search"
        )
    except Exception as e:
        return f"Search error: {e}"


def fetch_page(url: str, max_chars: int = 8000) -> str:
    """
    Fetch and extract text content from a URL.
    Returns plain text stripped of HTML.
    """
    if not url or not url.strip():
        return "Error: Empty URL."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; Lirox/2.0; +https://lirox.ai)"
            )
        }
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()

        soup = BeautifulSoup(res.text, "lxml")

        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        content = "\n".join(lines)

        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[Truncated at {max_chars:,} chars]"

        return content or "No text content found."

    except ImportError:
        return "beautifulsoup4/lxml not installed. Run: pip install beautifulsoup4 lxml"
    except Exception as e:
        return f"Fetch error: {e}"


def search_and_summarize(query: str) -> str:
    """
    Search the web and summarize results using the LLM.
    """
    raw_results = web_search(query, max_results=3)
    if raw_results.startswith("Error") or raw_results.startswith("No search"):
        return raw_results

    from lirox.utils.llm import generate_response

    prompt = (
        f"Summarize these search results for the query: '{query}'\n\n"
        f"{raw_results[:4000]}\n\n"
        "Give a concise, accurate summary of the key information found."
    )
    return generate_response(prompt)
