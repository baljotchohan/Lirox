"""
Lirox v0.8.5 — Free Public Data APIs (Phase 5)

Keyless, rate-limit-friendly access to real-time data sources:
- DuckDuckGo Instant Answer API
- Wikipedia REST API
- CoinGecko (crypto prices)
- wttr.in (weather)
- GitHub Search

All functions return clean structured dicts and NEVER crash on failure.
"""

import re
import json
import time
from typing import Optional, Dict, Any

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ─── Shared HTTP helper ──────────────────────────────────────────────────────

_SESSION = None

def _get_session():
    """Lazy-init shared requests session."""
    global _SESSION
    if _SESSION is None and _HAS_REQUESTS:
        import requests as rq
        _SESSION = rq.Session()
        _SESSION.headers.update({
            "User-Agent": "Lirox/0.8.5 (autonomous-agent; +https://github.com/lirox-ai/lirox)"
        })
    return _SESSION


def _get(url: str, params: dict = None, timeout: int = 8) -> Optional[dict]:
    """GET with timeout and silent error handling."""
    if not _HAS_REQUESTS:
        return None
    try:
        sess = _get_session()
        r = sess.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _get_text(url: str, params: dict = None, timeout: int = 8) -> Optional[str]:
    """GET returning plain text."""
    if not _HAS_REQUESTS:
        return None
    try:
        sess = _get_session()
        r = sess.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


# ─── DuckDuckGo Instant Answer ───────────────────────────────────────────────

def duckduckgo_instant(query: str) -> Dict[str, Any]:
    """
    Query DuckDuckGo Instant Answer API (no key needed).
    Returns abstract text, related topics, and an answer if available.
    """
    data = _get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
    )

    if not data:
        return {"status": "error", "source": "duckduckgo", "answer": ""}

    answer = (
        data.get("AbstractText")
        or data.get("Answer")
        or data.get("Definition")
        or ""
    )

    topics = []
    for t in data.get("RelatedTopics", [])[:5]:
        if isinstance(t, dict) and t.get("Text"):
            topics.append(t["Text"])

    return {
        "status": "success" if answer or topics else "empty",
        "source": "duckduckgo",
        "answer": answer,
        "related": topics,
        "url": data.get("AbstractURL", ""),
        "type": data.get("Type", ""),
    }


# ─── Wikipedia REST API ───────────────────────────────────────────────────────

def wikipedia_summary(query: str, lang: str = "en") -> Dict[str, Any]:
    """
    Fetch a Wikipedia article summary (no key needed).
    Auto-searches for the best matching article title.
    """
    # Try direct article fetch first
    slug = query.replace(" ", "_")
    data = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}")

    if not data or data.get("type") == "https://mediawiki.org/wiki/HyperSwitch/errors/not_found":
        # Try search to find best match
        search = _get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1,
            },
        )
        if search:
            results = search.get("query", {}).get("search", [])
            if results:
                title = results[0]["title"].replace(" ", "_")
                data = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}")

    if not data:
        return {"status": "error", "source": "wikipedia", "answer": ""}

    extract = data.get("extract", "")
    if not extract:
        return {"status": "empty", "source": "wikipedia", "answer": ""}

    return {
        "status": "success",
        "source": "wikipedia",
        "answer": extract[:1500],
        "title": data.get("title", query),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "thumbnail": data.get("thumbnail", {}).get("source", ""),
    }


# ─── CoinGecko Crypto Prices ──────────────────────────────────────────────────

_COINGECKO_SLUGS = {
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "solana": "solana",
    "sol": "solana",
    "dogecoin": "dogecoin",
    "doge": "dogecoin",
    "cardano": "cardano",
    "ada": "cardano",
    "xrp": "ripple",
    "ripple": "ripple",
    "bnb": "binancecoin",
    "binance": "binancecoin",
    "usdc": "usd-coin",
    "usdt": "tether",
}


def coingecko_price(coin: str, vs_currency: str = "usd") -> Dict[str, Any]:
    """
    Fetch live crypto price from CoinGecko (no key needed, public tier).
    """
    coin_lower = coin.lower().strip()
    coin_id = _COINGECKO_SLUGS.get(coin_lower, coin_lower)

    data = _get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": coin_id,
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
        },
    )

    if not data or coin_id not in data:
        return {"status": "error", "source": "coingecko", "answer": f"Could not fetch {coin} price."}

    coin_data = data[coin_id]
    price = coin_data.get(vs_currency, 0)
    change_24h = coin_data.get(f"{vs_currency}_24h_change", 0)
    market_cap = coin_data.get(f"{vs_currency}_market_cap", 0)

    direction = "▲" if change_24h >= 0 else "▼"
    answer = (
        f"{coin.upper()} price: ${price:,.2f} {vs_currency.upper()}\n"
        f"24h change: {direction} {abs(change_24h):.2f}%\n"
        f"Market cap: ${market_cap:,.0f}"
    )

    return {
        "status": "success",
        "source": "coingecko",
        "answer": answer,
        "price": price,
        "change_24h": change_24h,
        "market_cap": market_cap,
        "coin": coin_id,
        "currency": vs_currency,
    }


# ─── wttr.in Weather ──────────────────────────────────────────────────────────

def wttr_weather(location: str) -> Dict[str, Any]:
    """
    Fetch current weather from wttr.in (no key needed).
    Returns clean one-line summary.
    """
    text = _get_text(
        f"https://wttr.in/{location}",
        params={"format": "j1"},
        timeout=8,
    )

    if not text:
        # Fall back to simple format
        simple = _get_text(f"https://wttr.in/{location}?format=3", timeout=8)
        if simple:
            return {
                "status": "success",
                "source": "wttr.in",
                "answer": simple.strip(),
                "location": location,
            }
        return {"status": "error", "source": "wttr.in", "answer": ""}

    try:
        data = json.loads(text)
        cur = data["current_condition"][0]
        temp_c = cur["temp_C"]
        temp_f = cur["temp_F"]
        desc = cur["weatherDesc"][0]["value"]
        feels_c = cur["FeelsLikeC"]
        humidity = cur["humidity"]
        wind_kmph = cur["windspeedKmph"]

        area = data.get("nearest_area", [{}])[0]
        area_name = area.get("areaName", [{}])[0].get("value", location)
        country = area.get("country", [{}])[0].get("value", "")

        answer = (
            f"Weather in {area_name}, {country}:\n"
            f"{desc} — {temp_c}°C / {temp_f}°F\n"
            f"Feels like: {feels_c}°C | Humidity: {humidity}% | Wind: {wind_kmph} km/h"
        )

        return {
            "status": "success",
            "source": "wttr.in",
            "answer": answer,
            "temp_c": int(temp_c),
            "temp_f": int(temp_f),
            "description": desc,
            "location": f"{area_name}, {country}",
        }
    except (KeyError, ValueError, json.JSONDecodeError):
        return {"status": "error", "source": "wttr.in", "answer": "Could not parse weather data."}


# ─── GitHub Search ────────────────────────────────────────────────────────────

def github_search(query: str, search_type: str = "repositories") -> Dict[str, Any]:
    """
    Search GitHub (no key for basic public access, up to 10 req/min).
    search_type: 'repositories', 'users', or 'code'
    """
    data = _get(
        f"https://api.github.com/search/{search_type}",
        params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
    )

    if not data:
        return {"status": "error", "source": "github", "answer": ""}

    items = data.get("items", [])
    total = data.get("total_count", 0)

    if not items:
        return {"status": "empty", "source": "github", "answer": f"No {search_type} found for: {query}"}

    lines = [f"GitHub search '{query}' ({total:,} results):"]
    for r in items[:5]:
        name = r.get("full_name") or r.get("login") or r.get("path", "")
        stars = r.get("stargazers_count", "")
        desc = r.get("description") or r.get("bio") or ""
        star_str = f" ⭐ {stars:,}" if stars else ""
        lines.append(f"  • {name}{star_str}" + (f" — {desc[:60]}" if desc else ""))

    return {
        "status": "success",
        "source": "github",
        "answer": "\n".join(lines),
        "results": items[:5],
        "total": total,
    }


# ─── Smart Dispatcher ────────────────────────────────────────────────────────

_CRYPTO_PATTERN = re.compile(
    r"\b(bitcoin|btc|ethereum|eth|solana|sol|dogecoin|doge|cardano|ada|xrp|ripple|bnb|usdc|usdt)\b",
    re.IGNORECASE,
)
_WEATHER_PATTERN = re.compile(
    r"\b(weather|temperature|forecast|rain|sunny|cloudy|humidity|wind)\b",
    re.IGNORECASE,
)
_GITHUB_PATTERN = re.compile(
    r"\b(github|repo|repository|repositories|open.?source|starred)\b",
    re.IGNORECASE,
)


def get_free_data(query: str) -> Dict[str, Any]:
    """
    Smart dispatcher — detects intent and calls the right free API.
    Returns a {status, source, answer, ...} dict.

    Priority:
    1. Crypto price query → CoinGecko
    2. Weather query → wttr.in
    3. GitHub query → GitHub Search
    4. Everything else → DuckDuckGo then Wikipedia
    """
    q_lower = query.lower()

    # 1. Crypto price
    m = _CRYPTO_PATTERN.search(q_lower)
    if m and any(kw in q_lower for kw in ["price", "cost", "worth", "value", "how much", "usd", "$"]):
        result = coingecko_price(m.group(0))
        if result["status"] == "success":
            return result

    # 2. Weather
    if _WEATHER_PATTERN.search(q_lower):
        # Extract location: take words that aren't weather keywords
        stop = {"weather", "temperature", "forecast", "in", "at", "for", "the", "what", "is",
                "how", "today", "now", "current", "currently"}
        words = [w for w in query.split() if w.lower() not in stop]
        location = " ".join(words[:3]) if words else "London"
        result = wttr_weather(location)
        if result["status"] == "success":
            return result

    # 3. GitHub
    if _GITHUB_PATTERN.search(q_lower):
        result = github_search(query)
        if result["status"] == "success":
            return result

    # 4. DuckDuckGo instant answer
    ddg = duckduckgo_instant(query)
    if ddg.get("answer") or ddg.get("related"):
        return ddg

    # 5. Wikipedia summary as rich fallback
    wiki = wikipedia_summary(query)
    if wiki.get("status") == "success":
        return wiki

    return {"status": "empty", "source": "free_apis", "answer": ""}
