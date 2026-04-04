"""Stock Screening Tool."""
import json


def screen_stocks(criteria: str) -> str:
    try:
        import yfinance as yf

        tickers = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA",
            "JPM", "JNJ", "V", "PG", "UNH", "HD", "NFLX", "AMD",
        ]
        results = []
        for tk in tickers:
            try:
                info = yf.Ticker(tk).info
                results.append(
                    {
                        "ticker": tk,
                        "name": info.get("longName", tk),
                        "price": info.get("currentPrice"),
                        "pe": info.get("trailingPE"),
                        "market_cap": info.get("marketCap"),
                        "sector": info.get("sector"),
                    }
                )
            except Exception:
                continue
        return json.dumps(
            {"criteria": criteria, "results": results[:15]}, indent=2, default=str
        )
    except ImportError:
        return "yfinance not installed."
    except Exception as e:
        return f"Screener error: {e}"
