"""
Stage 1 Agent — Data Retrieval Agent.
"""

import logging
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from app.tools.data_fetch import fetch_all_data

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
            all_data = fetch_all_data(ticker)

            state_delta = {
                "financial_data": {
                    "ticker": ticker.upper(),
                    "company_profile": all_data["company_profile"],
                    "cash_flow": all_data["cash_flow"],
                    "dividend_history": all_data["dividend_history"],
                    "price_history": all_data["price_history"],
                    "ohlc_data": all_data["ohlc_data"],
                },
                "balance_sheet_data": all_data["balance_sheet_data"],
                "income_statement_data": all_data["income_statement_data"],
                "key_statistics": all_data["key_statistics"],
                "insider_transactions": all_data["insider_transactions"],
                "price_trend_data": all_data["price_trend_data"],
                "financial_data_error": None,
            }

            ctx.session.state.update(state_delta)
            yield Event(author=self.name, text=f"Fetched data for {ticker}", actions=EventActions(state_delta=state_delta))

        except Exception as e:
            logger.error(f"DataRetrievalAgent failed: {e}", exc_info=True)
            ctx.session.state["financial_data_error"] = str(e)
            yield Event(author=self.name, text=f"Data retrieval failed: {e}", actions=EventActions(state_delta={"financial_data_error": str(e)}))
