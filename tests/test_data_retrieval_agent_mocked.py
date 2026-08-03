"""
Mocked test for DataRetrievalAgent's core logic: correctly unwrapping MCP
CallToolResult shapes and correctly detecting failure vs success.

This exists specifically to guard against the regression found during
live integration testing: the agent originally reported "success" while
every field was silently empty, because it didn't know the real MCP
result shape ({"content": [...], "isError": bool}) and just checked for
raised exceptions / a simpler {"error": ...} dict that never actually
occurs in practice.

This test mocks McpToolset entirely, so it runs instantly with no
network and no subprocess -- use test_data_retrieval_agent.py (real
Runner + real MCP subprocess + real yfinance) for the full integration
check, which requires internet access.

Run with: python3 test_data_retrieval_agent_mocked.py
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.data_retrieval_agent import DataRetrievalAgent


def _make_success_result(data: dict) -> dict:
    """Builds a fake CallToolResult in the real observed success shape."""
    return {"content": [{"type": "text", "text": json.dumps(data)}], "isError": False}


def _make_error_result(message: str) -> dict:
    """Builds a fake CallToolResult in the real observed error shape."""
    return {"content": [{"type": "text", "text": f"Error executing tool: {message}"}], "isError": True}


def _mock_tool(name: str, result: dict):
    tool = MagicMock()
    tool.name = name
    tool.run_async = AsyncMock(return_value=result)
    return tool


async def _run_agent_with_mocked_tools(tools_by_result: dict):
    """
    tools_by_result: dict of tool_name -> fake CallToolResult dict
    Returns the final session.state after running DataRetrievalAgent.
    """
    fake_tools = [_mock_tool(name, result) for name, result in tools_by_result.items()]

    with patch("agents.data_retrieval_agent.MCPToolset") as MockToolsetClass:
        mock_toolset_instance = MagicMock()
        mock_toolset_instance.get_tools = AsyncMock(return_value=fake_tools)
        mock_toolset_instance.close = AsyncMock()
        MockToolsetClass.return_value = mock_toolset_instance

        agent = DataRetrievalAgent()
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="test", user_id="u", state={"ticker": "TEST"}
        )
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        async for _ in runner.run_async(
            user_id="u",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text="go")]),
        ):
            pass

        final_session = await session_service.get_session(
            app_name="test", user_id="u", session_id=session.id
        )
        return final_session.state


def test_all_tools_succeed():
    tools = {
        "get_company_profile": _make_success_result({"ticker": "TEST", "current_price": 100.0}),
        "get_cash_flow_statement": _make_success_result({"ticker": "TEST", "operating_cash_flow_by_year": {"2025": 1.0}}),
        "get_price_history": _make_success_result({"ticker": "TEST", "latest_close": 100.0}),
        "get_dividend_history": _make_success_result({"ticker": "TEST", "annual_dividends_per_share": {"2025": 1.0}}),
    }
    state = asyncio.run(_run_agent_with_mocked_tools(tools))

    assert state.get("financial_data_error") is None, f"Unexpected error: {state.get('financial_data_error')}"
    data = state["financial_data"]
    assert data["company_profile"]["current_price"] == 100.0
    assert data["dividend_history"]["annual_dividends_per_share"]["2025"] == 1.0
    print("test_all_tools_succeed PASSED")


def test_company_profile_failure_is_detected():
    """
    This is the exact regression case: a failed company_profile call must
    NOT be reported as success. Before the fix, this would have passed
    incorrectly because the isError/JSON-wrapped shape wasn't checked.
    """
    tools = {
        "get_company_profile": _make_error_result("Expecting value: line 1 column 1 (char 0)"),
        "get_cash_flow_statement": _make_success_result({"ticker": "TEST", "operating_cash_flow_by_year": {"2025": 1.0}}),
        "get_price_history": _make_success_result({"ticker": "TEST", "latest_close": 100.0}),
        "get_dividend_history": _make_success_result({"ticker": "TEST", "annual_dividends_per_share": {"2025": 1.0}}),
    }
    state = asyncio.run(_run_agent_with_mocked_tools(tools))

    assert state.get("financial_data_error") is not None, (
        "REGRESSION: a failed get_company_profile call was not detected -- "
        "this is the exact silent-failure bug found during live testing."
    )
    assert "get_company_profile" in state["financial_data_error"]
    assert state.get("financial_data") is None
    print("test_company_profile_failure_is_detected PASSED")


def test_dividend_failure_does_not_block_other_data():
    """Non-dividend-paying stocks are an expected case, not a system error."""
    tools = {
        "get_company_profile": _make_success_result({"ticker": "TEST", "current_price": 100.0}),
        "get_cash_flow_statement": _make_success_result({"ticker": "TEST", "operating_cash_flow_by_year": {"2025": 1.0}}),
        "get_price_history": _make_success_result({"ticker": "TEST", "latest_close": 100.0}),
        "get_dividend_history": _make_error_result("No dividend history found"),
    }
    state = asyncio.run(_run_agent_with_mocked_tools(tools))

    assert state.get("financial_data_error") is None
    data = state["financial_data"]
    assert data["dividend_history"] is None
    assert data["dividend_history_error"] is not None
    print("test_dividend_failure_does_not_block_other_data PASSED")


def test_success_result_is_json_unwrapped_correctly():
    """Confirms the JSON-string-inside-content unwrapping actually works, not just error detection."""
    tools = {
        "get_company_profile": _make_success_result({
            "ticker": "TEST", "long_name": "Test Corp", "beta": 1.23, "market_cap": 999
        }),
        "get_cash_flow_statement": _make_success_result({"ticker": "TEST", "operating_cash_flow_by_year": {"2025": 500.0}}),
        "get_price_history": _make_success_result({"ticker": "TEST", "latest_close": 55.5}),
        "get_dividend_history": _make_success_result({"ticker": "TEST", "annual_dividends_per_share": {"2025": 2.0}}),
    }
    state = asyncio.run(_run_agent_with_mocked_tools(tools))
    profile = state["financial_data"]["company_profile"]

    assert profile["long_name"] == "Test Corp"
    assert profile["beta"] == 1.23
    assert profile["market_cap"] == 999
    print("test_success_result_is_json_unwrapped_correctly PASSED")


if __name__ == "__main__":
    test_all_tools_succeed()
    test_company_profile_failure_is_detected()
    test_dividend_failure_does_not_block_other_data()
    test_success_result_is_json_unwrapped_correctly()
    print("\nAll mocked DataRetrievalAgent tests passed.")
