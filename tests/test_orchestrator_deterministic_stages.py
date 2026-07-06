"""
End-to-end test of the ValuAgent pipeline's four DETERMINISTIC agents
(DataRetrievalAgent -> ValuationAgent -> SensitivityAgent -> CriticAgent),
run together as a single SequentialAgent to confirm state correctly
hands off between all four stages in one real run.

The fifth agent (MemoWriterAgent, in the real orchestrator.py) is
deliberately excluded here and tested separately in
test_memo_writer_agent_live.py, because it requires a real Gemini API
key and network access, neither available in the build sandbox. This
test uses a SEPARATE SequentialAgent (not agents.orchestrator.root_agent)
containing only the four deterministic stages, specifically so this test
can run with zero external dependencies except a mocked MCP call.

To test the COMPLETE pipeline including the memo (all 5 stages, using
the real agents.orchestrator.root_agent), see run_valuagent.py, which
requires both internet access (for MCP/yfinance) AND a Gemini API key.

Run with: python3 test_orchestrator_deterministic_stages.py
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from google.adk import Runner
from google.adk.agents import SequentialAgent
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.data_retrieval_agent import DataRetrievalAgent
from agents.valuation_agent import ValuationAgent
from agents.sensitivity_agent import SensitivityAgent
from agents.critic_agent import CriticAgent


def _make_success_result(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data)}], "isError": False}


def _mock_tool(name: str, result: dict):
    tool = MagicMock()
    tool.name = name
    tool.run_async = AsyncMock(return_value=result)
    return tool


# Realistic mocked MCP responses, shaped like real AAPL data from the
# Phase 2 live test (round numbers for readability).
MOCKED_MCP_RESULTS = {
    "get_company_profile": _make_success_result({
        "ticker": "TESTCO", "long_name": "Test Company Inc.",
        "current_price": 300.0, "market_cap": 4_500_000_000_000,
        "beta": 1.1, "shares_outstanding": 15_000_000_000,
        "total_debt": 85_000_000_000, "total_cash": 68_000_000_000,
    }),
    "get_cash_flow_statement": _make_success_result({
        "ticker": "TESTCO",
        "operating_cash_flow_by_year": {
            "2022": 122_000_000_000, "2023": 110_000_000_000,
            "2024": 118_000_000_000, "2025": 111_000_000_000,
        },
        "capital_expenditure_by_year": {
            "2022": -10_700_000_000, "2023": -10_900_000_000,
            "2024": -9_400_000_000, "2025": -12_700_000_000,
        },
    }),
    "get_price_history": _make_success_result({
        "ticker": "TESTCO", "latest_close": 300.0, "close_by_date": {},
    }),
    "get_dividend_history": _make_success_result({
        "ticker": "TESTCO",
        "annual_dividends_per_share": {
            "2022": 0.91, "2023": 0.95, "2024": 0.99, "2025": 1.03, "2026": 0.53,
        },
    }),
}


async def run_pipeline():
    fake_tools = [_mock_tool(name, result) for name, result in MOCKED_MCP_RESULTS.items()]

    with patch("agents.data_retrieval_agent.McpToolset") as MockToolsetClass:
        mock_toolset_instance = MagicMock()
        mock_toolset_instance.get_tools = AsyncMock(return_value=fake_tools)
        mock_toolset_instance.close = AsyncMock()
        MockToolsetClass.return_value = mock_toolset_instance

        pipeline = SequentialAgent(
            name="test_pipeline",
            sub_agents=[
                DataRetrievalAgent(),
                ValuationAgent(),
                SensitivityAgent(),
                CriticAgent(),
            ],
        )

        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="pipeline_test", user_id="u", state={"ticker": "TESTCO"}
        )
        runner = Runner(agent=pipeline, app_name="pipeline_test", session_service=session_service)

        print("--- Running 4-stage pipeline (mocked MCP, no network) ---\n")
        async for event in runner.run_async(
            user_id="u",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text="Value TESTCO")]),
        ):
            if event.content and event.content.parts and event.content.parts[0].text:
                print(f"[{event.author}] {event.content.parts[0].text}")

        final_session = await session_service.get_session(
            app_name="pipeline_test", user_id="u", session_id=session.id
        )
        return final_session.state


def test_full_deterministic_pipeline_runs_cleanly():
    state = asyncio.run(run_pipeline())

    assert state.get("financial_data_error") is None, state.get("financial_data_error")
    assert state.get("valuation_result_error") is None, state.get("valuation_result_error")
    assert state.get("sensitivity_result_error") is None, state.get("sensitivity_result_error")
    assert state.get("critic_flags_error") is None, state.get("critic_flags_error")

    assert state.get("financial_data") is not None
    assert state.get("valuation_result") is not None
    assert state.get("sensitivity_result") is not None
    assert state.get("critic_flags") is not None

    assert state["financial_data"]["ticker"] == "TESTCO"
    assert state["valuation_result"]["ticker"] == "TESTCO"
    assert abs(
        state["sensitivity_result"]["wacc_values"][2] - state["valuation_result"]["dcf_inputs_used"]["wacc"]
    ) < 1e-5, "Sensitivity grid's center WACC should match the WACC ValuationAgent actually used"

    print("\ntest_full_deterministic_pipeline_runs_cleanly PASSED")
    print(f"  DCF value/share: {state['valuation_result']['dcf']['value_per_share']:.2f}")
    print(f"  Critic flags raised: {len(state['critic_flags'])}")


if __name__ == "__main__":
    test_full_deterministic_pipeline_runs_cleanly()
