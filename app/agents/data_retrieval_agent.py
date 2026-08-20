"""
Stage 1 Agent — Data Retrieval Agent.
"""

import logging
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from app.tools.data_fetch import (
    get_company_profile,
    get_cash_flow_statement,
    get_dividend_history,
    get_price_history,
    get_balance_sheet,
    get_income_statement,
    get_key_statistics,
    get_insider_transactions,
    get_multi_period_price_history,
    get_ohlc_data,
)

logger = logging.getLogger(__name__)


class DataRetrievalAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="data_retrieval_agent")

    async def _run_async_impl(self, ctx):
        ticker = ctx.session.state.get("ticker")
        if not ticker:
            ctx.session.state["financial_data_error"] = "No ticker symbol provided in session state."
            return

        logger.info(f"DataRetrievalAgent running for ticker '{ticker}'...")

        try:
            profile = get_company_profile(ticker)
            cf = get_cash_flow_statement(ticker)
            div = get_dividend_history(ticker)
            price = get_price_history(ticker)
            bs = get_balance_sheet(ticker)
            inc = get_income_statement(ticker)
            stats = get_key_statistics(ticker)
            insider = get_insider_transactions(ticker)
            multi_price = get_multi_period_price_history(ticker)
            ohlc = get_ohlc_data(ticker)

            state_delta = {
                "financial_data": {
                    "ticker": ticker.upper(),
                    "company_profile": profile,
                    "cash_flow": cf,
                    "dividend_history": div,
                    "price_history": price,
                    "ohlc_data": ohlc,
                },
                "balance_sheet_data": bs,
                "income_statement_data": inc,
                "key_statistics": stats,
                "insider_transactions": insider.get("transactions", []),
                "price_trend_data": multi_price,
                "financial_data_error": None,
            }

            ctx.session.state.update(state_delta)
            yield Event(author=self.name, text=f"Fetched data for {ticker}", actions=EventActions(state_delta=state_delta))

        except Exception as e:
            logger.error(f"DataRetrievalAgent failed: {e}", exc_info=True)
            ctx.session.state["financial_data_error"] = str(e)
            yield Event(author=self.name, text=f"Data retrieval failed: {e}", actions=EventActions(state_delta={"financial_data_error": str(e)}))
