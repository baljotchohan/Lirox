"""Financial Statements — yfinance based."""
import json


def get_fundamentals(ticker: str, statement_type: str = "all") -> str:
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        result = {"ticker": ticker}

        if statement_type in ("income", "all"):
            try:
                inc = stock.income_stmt
                if inc is not None and not inc.empty:
                    result["income"] = {
                        str(idx): [_s(inc.loc[idx, c]) for c in inc.columns[:4]]
                        for idx in list(inc.index)[:8]
                    }
            except Exception:
                result["income"] = "unavailable"

        if statement_type in ("balance", "all"):
            try:
                bal = stock.balance_sheet
                if bal is not None and not bal.empty:
                    result["balance"] = {
                        str(idx): [_s(bal.loc[idx, c]) for c in bal.columns[:4]]
                        for idx in list(bal.index)[:8]
                    }
            except Exception:
                result["balance"] = "unavailable"

        if statement_type in ("cashflow", "all"):
            try:
                cf = stock.cashflow
                if cf is not None and not cf.empty:
                    result["cashflow"] = {
                        str(idx): [_s(cf.loc[idx, c]) for c in cf.columns[:4]]
                        for idx in list(cf.index)[:8]
                    }
            except Exception:
                result["cashflow"] = "unavailable"

        return json.dumps(result, indent=2, default=str)
    except ImportError:
        return "yfinance not installed."
    except Exception as e:
        return f"Error: {e}"


def _s(v) -> str:
    try:
        if v is None or str(v) == "nan":
            return "N/A"
        n = float(v)
        if abs(n) >= 1e9:
            return f"{n/1e9:.1f}B"
        if abs(n) >= 1e6:
            return f"{n/1e6:.1f}M"
        return f"{n:,.0f}"
    except Exception:
        return str(v)
