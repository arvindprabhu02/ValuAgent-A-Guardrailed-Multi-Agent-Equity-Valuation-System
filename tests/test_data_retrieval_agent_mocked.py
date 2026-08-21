"""
Mocked unit tests for DataRetrievalAgent.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from app.agents.data_retrieval_agent import DataRetrievalAgent


def test_data_retrieval_agent_success():
    async def _test():
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            session_id="test_retrieval_session",
            app_name="agents",
            user_id="test_user",
            state={"ticker": "AAPL"}
        )

        with patch("app.agents.data_retrieval_agent.get_company_profile", return_value={"ticker": "AAPL", "current_price": 198.5}), \
             patch("app.agents.data_retrieval_agent.get_cash_flow_statement", return_value={"ticker": "AAPL"}), \
             patch("app.agents.data_retrieval_agent.get_dividend_history", return_value={"ticker": "AAPL"}), \
             patch("app.agents.data_retrieval_agent.get_price_history", return_value={"ticker": "AAPL"}), \
             patch("app.agents.data_retrieval_agent.get_balance_sheet", return_value={"ticker": "AAPL"}), \
             patch("app.agents.data_retrieval_agent.get_income_statement", return_value={"ticker": "AAPL"}), \
             patch("app.agents.data_retrieval_agent.get_key_statistics", return_value={"ticker": "AAPL", "trailing_pe": 30.0}), \
             patch("app.agents.data_retrieval_agent.get_insider_transactions", return_value={"ticker": "AAPL", "transactions": []}), \
             patch("app.agents.data_retrieval_agent.get_multi_period_price_history", return_value={"ticker": "AAPL", "return_1y_pct": 25.0}), \
             patch("app.agents.data_retrieval_agent.get_ohlc_data", return_value={"dates": [], "closes": []}):
            agent = DataRetrievalAgent()
            runner = Runner(agent=agent, session_service=session_service, app_name="agents")
            msg = Content(parts=[Part(text="Run Retrieval")])

            async for _ in runner.run_async(session_id=session.id, user_id="test_user", new_message=msg):
                pass

        final_session = await session_service.get_session(session_id=session.id, app_name="agents", user_id="test_user")
        assert final_session.state.get("financial_data_error") is None
        assert "financial_data" in final_session.state

    asyncio.run(_test())
