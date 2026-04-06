"""
Lirox — Finance Agent
Full market analyst: Buffett value × Renaissance quantitative.
Sub-agent pipeline: Data Collector → Technical Analyst → Fundamental Analyst → Risk Manager → Synthesizer
BUG-05 FIX: Strict validation on LLM tool routing response
BUG-14 FIX: Pattern strings truncated to 30 chars before .upper()
"""
from __future__ import annotations

import json
import os
import re
from typing import Generator, Dict, Any

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.config import MAX_LLM_PROMPT_CHARS

FINANCE_SYS = """
═══════════════════════════════════════════
  YOU ARE: {agent_name} Finance Agent
  IDENTITY: World-class financial analyst
  PHILOSOPHY: Buffett value + Simons quantitative
═══════════════════════════════════════════
NEVER pretend to be another agent. NEVER route tasks away in your response.

MANDATORY ANALYSIS FRAMEWORK:
Before answering ANY financial question, consider:

1. FUNDAMENTAL ANALYSIS
   - Revenue growth (YoY, QoQ), EPS, forward EPS
   - P/E, P/B, P/S, EV/EBITDA ratios
   - Debt/Equity, Current Ratio, Free Cash Flow yield
   - Return on Equity (ROE), Return on Capital (ROIC)

2. TECHNICAL ANALYSIS (for price questions)
   - Trend: 50-day MA vs 200-day MA (golden/death cross)
   - RSI (14): overbought >70, oversold <30
   - MACD signal line crossover
   - Support/resistance levels

3. RISK ASSESSMENT
   - Beta (market risk), Max drawdown, Volatility
   - Margin of safety (DCF fair value vs current price)

4. CATALYSTS & NEWS
   - Upcoming earnings, analyst ratings, insider activity

5. RECOMMENDATION
   - Clear BUY / HOLD / SELL with price target
   - Position sizing suggestion, stop-loss level, time horizon

FORMAT: Lead with the most critical number. Use compact tables.
Always caveat: "This is not financial advice. Do your own research."

Date: {date}
{user_context}
"""

ONBOARDING_MSG = """📊 **Welcome to your Finance Agent!**

I'm your personal financial analyst — Warren Buffett meets Renaissance Technologies.

To make me more powerful, you can add:
  • **`FINANCIAL_DATASETS_API_KEY`** — Real SEC filings, fundamentals data
  • **`TAVILY_API_KEY`** — Real-time financial news and research
  • **`ALPHA_VANTAGE_API_KEY`** — Intraday data (25 calls/day free)
  • **`POLYGON_API_KEY`** — Real-time options + news

Without these, I use yfinance for live prices, history, and fundamentals.

What's your first financial question?"""


class FinanceAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "finance"

    @property
    def description(self) -> str:
        return "Market analysis, stock research, portfolio insights, valuation, risk"

    def get_onboarding_message(self) -> str:
        return ONBOARDING_MSG

    def _get_proactive_greeting(self) -> str:
        patterns = self.memory.get_pattern_insights(limit=1)
        if not patterns:
            return ""
        # BUG-14 FIX: Truncate pattern string to 30 chars before .upper()
        topic = patterns[0][:30].upper()
        import random
        templates = [
            f"💡 Last time you asked about **{topic}** — want a quick update?",
            f"📈 You've been tracking **{topic}** — here's what I'd check first today:",
        ]
        return random.choice(templates)

    def run(
        self, query: str, system_prompt: str = "", context: str = "", mode: str = "complex"
    ) -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time
        from datetime import datetime

        logger = get_logger(f"lirox.agents.{self.name}")
        start  = time.time()
        log_with_metadata(logger, "INFO", "Finance Agent started", query=query[:100])

        if len(self.memory.conversation_buffer) > 0:
            greeting = self._get_proactive_greeting()
            if greeting:
                yield {"type": "agent_progress", "message": greeting}

        # Step 1: Data Collection
        yield {"type": "agent_progress", "message": "📡 Collecting market data..."}
        raw_data = self._collect_data(query)

        # Step 2: Technical Analysis
        yield {"type": "agent_progress", "message": "📈 Running technical analysis..."}
        technicals = self._technical_analysis(raw_data)

        # Step 3: Fundamental Analysis
        yield {"type": "agent_progress", "message": "🔢 Analyzing fundamentals..."}
        fundamentals = self._fundamental_analysis(raw_data)

        # Step 4: Risk Assessment
        yield {"type": "agent_progress", "message": "⚠️ Assessing risk..."}
        risk = self._risk_assessment(raw_data, technicals)

        # Step 5: Synthesize
        yield {"type": "agent_progress", "message": "💡 Synthesizing recommendation..."}

        # Build system prompt
        agent_name   = self.profile_data.get("agent_name", "Lirox")
        user_context = ""
        mem_ctx      = self.memory.get_relevant_context(query)
        if mem_ctx:
            user_context = f"User Context:\n{mem_ctx}"

        sys_p = FINANCE_SYS.format(
            agent_name   = agent_name,
            date         = datetime.now().strftime("%B %d, %Y"),
            user_context = user_context,
        )

        synth_prompt = (
            f"Query: {query}\n\n"
            f"Market Data:\n{json.dumps(raw_data.get('_summary', {}), indent=2, default=str)[:3000]}\n\n"
            f"Technical Indicators:\n{json.dumps(technicals, indent=2, default=str)[:2000]}\n\n"
            f"Fundamentals:\n{json.dumps(fundamentals, indent=2, default=str)[:2000]}\n\n"
            f"Risk Assessment:\n{json.dumps(risk, indent=2, default=str)[:1000]}"
        )
        if context:
            synth_prompt += f"\n\nReasoning context:\n{context[:1000]}"

        answer = generate_response(
            synth_prompt[:MAX_LLM_PROMPT_CHARS],
            provider="auto",
            system_prompt=sys_p,
        )
        self.memory.save_exchange(query, answer)

        log_with_metadata(logger, "INFO", "Finance Agent completed",
                          duration_ms=int((time.time() - start) * 1000))
        yield {"type": "done", "answer": answer, "sources": []}

    # ─── Sub-agent: Data Collector ────────────────────────────────────────────

    def _collect_data(self, query: str) -> dict:
        data: dict = {"_summary": {}}
        tickers = self._extract_tickers(query)

        for ticker in tickers[:5]:
            try:
                import yfinance as yf
                t = yf.Ticker(ticker)
                info = t.info or {}
                hist = t.history(period="6mo")
                fin  = t.financials
                bs   = t.balance_sheet
                cf   = t.cashflow
                rec  = t.recommendations

                data[ticker] = {
                    "info": {k: v for k, v in info.items() if isinstance(v, (str, int, float, bool))},
                    "history": hist.tail(30).to_dict() if not hist.empty else {},
                    "financials": fin.to_dict() if fin is not None and not fin.empty else {},
                    "balance_sheet": bs.to_dict() if bs is not None and not bs.empty else {},
                    "cashflow": cf.to_dict() if cf is not None and not cf.empty else {},
                    "recommendations": rec.tail(5).to_dict() if rec is not None and not rec.empty else {},
                }
                # Quick summary for synthesizer
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                data["_summary"][ticker] = {
                    "price":    f"${price:,.2f}" if price else "N/A",
                    "name":     info.get("longName", ticker),
                    "sector":   info.get("sector", "N/A"),
                    "pe":       info.get("trailingPE"),
                    "mktcap":   info.get("marketCap"),
                }
            except Exception as e:
                data["_summary"][ticker] = {"error": str(e)}

        # Bitcoin special case
        if "bitcoin" in query.lower() or "btc" in query.lower():
            try:
                import yfinance as yf
                btc = yf.Ticker("BTC-USD")
                btc_price = getattr(btc.fast_info, "last_price", None)
                if btc_price:
                    data["_summary"]["BTC"] = {"price": f"${btc_price:,.0f}", "name": "Bitcoin"}
            except Exception:
                pass

        # Optional: Tavily news
        if os.getenv("TAVILY_API_KEY"):
            data["news"] = self._fetch_news_tavily(query)
        else:
            # Fallback: DDG news search
            try:
                data["news"] = self.search_web(f"{query} financial news recent")[:2000]
            except Exception:
                data["news"] = ""

        return data

    def _extract_tickers(self, query: str) -> list:
        """Extract stock tickers from query text."""
        # Common non-ticker uppercase words to filter
        stopwords = {"A", "I", "AN", "THE", "AND", "FOR", "IN", "ON", "AT", "TO",
                     "IS", "IT", "MY", "ME", "BE", "DO", "GO", "IF", "OR", "SO",
                     "BY", "UP", "US", "WE", "NO", "OH", "OF", "AS", "AM",
                     "ETF", "IPO", "CEO", "CFO", "CTO", "API"}
        found = re.findall(r'\b[A-Z]{2,5}\b', query)
        return [t for t in found if t not in stopwords][:5]

    def _fetch_news_tavily(self, query: str) -> str:
        try:
            from lirox.tools.search.tavily import search_tavily
            return search_tavily(f"{query} financial news")[:2000]
        except Exception:
            return ""

    # ─── Sub-agent: Technical Analysis ───────────────────────────────────────

    def _technical_analysis(self, raw_data: dict) -> dict:
        results = {}
        for ticker, d in raw_data.items():
            if ticker in ("news", "_summary"):
                continue
            hist = d.get("history", {})
            if not hist:
                continue
            try:
                import pandas as pd
                df = pd.DataFrame(hist)
                # Columns may be multiindex when converted from yfinance
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                close = df.get("Close")
                if close is None or len(close) < 14:
                    continue

                # RSI
                delta = close.diff()
                gain  = delta.clip(lower=0).rolling(14).mean()
                loss  = (-delta.clip(upper=0)).rolling(14).mean()
                rs    = gain / (loss + 1e-9)
                rsi   = 100 - (100 / (1 + rs))

                # Moving averages
                ma50  = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
                ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

                # MACD
                ema12  = close.ewm(span=12).mean()
                ema26  = close.ewm(span=26).mean()
                macd   = ema12 - ema26
                signal = macd.ewm(span=9).mean()

                results[ticker] = {
                    "rsi":             round(float(rsi.iloc[-1]), 2),
                    "rsi_signal":      "OVERBOUGHT" if rsi.iloc[-1] > 70 else ("OVERSOLD" if rsi.iloc[-1] < 30 else "NEUTRAL"),
                    "ma50":            round(float(ma50), 2) if ma50 and not pd.isna(ma50) else None,
                    "ma200":           round(float(ma200), 2) if ma200 and not pd.isna(ma200) else None,
                    "macd":            round(float(macd.iloc[-1]), 4),
                    "macd_signal":     round(float(signal.iloc[-1]), 4),
                    "macd_histogram":  round(float((macd - signal).iloc[-1]), 4),
                    "trend":           "BULLISH" if (ma50 and ma200 and float(ma50) > float(ma200)) else "BEARISH",
                    "price_now":       round(float(close.iloc[-1]), 2),
                    "price_30d_ago":   round(float(close.iloc[0]), 2) if len(close) >= 30 else None,
                }
            except Exception:
                pass
        return results

    # ─── Sub-agent: Fundamental Analysis ─────────────────────────────────────

    def _fundamental_analysis(self, raw_data: dict) -> dict:
        results = {}
        for ticker, d in raw_data.items():
            if ticker in ("news", "_summary"):
                continue
            info = d.get("info", {})
            if not info:
                continue
            try:
                results[ticker] = {
                    "pe_trailing":   info.get("trailingPE"),
                    "pe_forward":    info.get("forwardPE"),
                    "pb_ratio":      info.get("priceToBook"),
                    "ps_ratio":      info.get("priceToSalesTrailing12Months"),
                    "ev_ebitda":     info.get("enterpriseToEbitda"),
                    "roe":           info.get("returnOnEquity"),
                    "roa":           info.get("returnOnAssets"),
                    "debt_equity":   info.get("debtToEquity"),
                    "current_ratio": info.get("currentRatio"),
                    "fcf_yield":     info.get("freeCashflow"),
                    "revenue_growth":info.get("revenueGrowth"),
                    "eps_trailing":  info.get("trailingEps"),
                    "eps_forward":   info.get("forwardEps"),
                    "dividend_yield":info.get("dividendYield"),
                    "market_cap":    info.get("marketCap"),
                    "sector":        info.get("sector"),
                    "industry":      info.get("industry"),
                    "52w_high":      info.get("fiftyTwoWeekHigh"),
                    "52w_low":       info.get("fiftyTwoWeekLow"),
                    "analyst_target":info.get("targetMeanPrice"),
                    "recommendation":info.get("recommendationKey"),
                }
            except Exception:
                pass
        return results

    # ─── Sub-agent: Risk Assessment ───────────────────────────────────────────

    def _risk_assessment(self, raw_data: dict, technicals: dict) -> dict:
        results = {}
        for ticker, d in raw_data.items():
            if ticker in ("news", "_summary"):
                continue
            info = d.get("info", {})
            tech = technicals.get(ticker, {})
            try:
                beta = info.get("beta", 1.0)
                risk_level = "LOW"
                if beta and float(beta) > 1.5:
                    risk_level = "HIGH"
                elif beta and float(beta) > 1.0:
                    risk_level = "MEDIUM"

                results[ticker] = {
                    "beta":           beta,
                    "risk_level":     risk_level,
                    "volatility_30d": info.get("beta"),  # proxy
                    "52w_range_pos":  None,
                    "rsi_risk":       tech.get("rsi_signal", "NEUTRAL"),
                    "trend":          tech.get("trend", "UNKNOWN"),
                }
                # Compute 52-week range position
                h, l, price = info.get("fiftyTwoWeekHigh"), info.get("fiftyTwoWeekLow"), info.get("currentPrice")
                if all([h, l, price]) and float(h) != float(l):
                    pos = (float(price) - float(l)) / (float(h) - float(l)) * 100
                    results[ticker]["52w_range_pos"] = f"{pos:.0f}% of range"
            except Exception:
                pass
        return results

    # ─── BUG-05 FIX helpers ───────────────────────────────────────────────────

    def _parse_tools(self, text: str) -> list:
        """BUG-05 FIX: Strict validation — if response looks hallucinated, return []."""
        # If response is very long or has no JSON array indicator, skip routing
        if len(text) > 500 or "[" not in text:
            return []
        text = re.sub(r"```json?\s*", "", text.strip())
        text = re.sub(r"```\s*", "", text)
        try:
            r = json.loads(text)
            return r if isinstance(r, list) else []
        except Exception:
            pass
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return []
