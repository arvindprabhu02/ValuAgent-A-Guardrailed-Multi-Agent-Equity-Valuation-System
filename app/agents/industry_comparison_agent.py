"""
Stage 3 Agent — Industry Comparison Agent.
"""

import logging
import yfinance as yf
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions

logger = logging.getLogger(__name__)

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Information Technology": "XLK",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
    "Materials": "XLB",
}


class IndustryComparisonAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="industry_comparison_agent")

    async def _run_async_impl(self, ctx):
        logger.info("IndustryComparisonAgent executing...")
        
        fin = ctx.session.state.get("financial_data", {})
        profile = fin.get("company_profile", {})
        price_trend = ctx.session.state.get("price_trend_data", {})
        
        sector = profile.get("sector") or "Technology"
        industry = profile.get("industry") or "General"
        etf_ticker = SECTOR_ETF_MAP.get(sector, "SPY")

        comp_1y_return = price_trend.get("return_1y_pct") or 0.0

        etf_1y_return = 0.0
        try:
            t_etf = yf.Ticker(etf_ticker)
            hist = t_etf.history(period="1y")
            if hist is not None and not hist.empty:
                closes = hist["Close"]
                p_start = float(closes.iloc[0])
                p_end = float(closes.iloc[-1])
                if p_start > 0:
                    etf_1y_return = ((p_end - p_start) / p_start) * 100.0
        except Exception as e:
            logger.warning(f"Could not fetch ETF data for '{etf_ticker}': {e}")

        outperformance = comp_1y_return - etf_1y_return

        ind_comp = {
            "sector": sector,
            "industry": industry,
            "sector_etf_ticker": etf_ticker,
            "company_1y_return_pct": comp_1y_return,
            "sector_etf_1y_return_pct": etf_1y_return,
            "outperformance_pct": outperformance,
            "is_outperforming": outperformance > 0,
        }

        ctx.session.state["industry_comparison"] = ind_comp
        yield Event(author=self.name, text=f"Benchmarked against {etf_ticker}.", actions=EventActions(state_delta={"industry_comparison": ind_comp}))
