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

        mock_toolset_instance = AsyncMock()
        
        def make_tool_res(data):
            res = MagicMock()
            res.content = [MagicMock(text=data)]
            return res

        mock_toolset_instance.call_tool.side_effect = lambda tool, args: {
            "fetch_company_profile": make_tool_res('{"ticker":"AAPL","current_price":198.5}'),
            "fetch_cash_flow_statement": make_tool_res('{"ticker":"AAPL","operating_cash_flow_by_year":{"2024":100}}'),
            "fetch_dividend_history": make_tool_res('{"ticker":"AAPL","has_dividends":true}'),
            "fetch_price_history": make_tool_res('{"ticker":"AAPL","latest_close":198.5}'),
            "fetch_balance_sheet": make_tool_res('{"ticker":"AAPL","total_assets":{"2024":500}}'),
            "fetch_income_statement": make_tool_res('{"ticker":"AAPL","total_revenue":{"2024":1000}}'),
            "fetch_key_statistics": make_tool_res('{"ticker":"AAPL","trailing_pe":30.0}'),
            "fetch_insider_transactions": make_tool_res('{"ticker":"AAPL","transactions":[]}'),
            "fetch_multi_period_price_history": make_tool_res('{"ticker":"AAPL","return_1y_pct":25.0}'),
        }[tool]

        with patch("app.agents.data_retrieval_agent.MCPToolset", return_value=mock_toolset_instance):
            agent = DataRetrievalAgent()
            runner = Runner(agent=agent, session_service=session_service, app_name="agents")
            msg = Content(parts=[Part(text="Run Retrieval")])

            async for _ in runner.run_async(session_id=session.id, user_id="test_user", new_message=msg):
                pass

        final_session = await session_service.get_session(session_id=session.id, app_name="agents", user_id="test_user")
        assert final_session.state.get("financial_data_error") is None
        assert "financial_data" in final_session.state

    asyncio.run(_test())
