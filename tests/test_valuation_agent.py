"""
Tests for ValuationAgent using realistic financial_data shaped exactly
like what DataRetrievalAgent produces (based on the REAL AAPL data shape
confirmed during the Phase 2 live test) -- no network or MCP subprocess
needed here, since this agent only depends on session state already
being populated.

Run with: python3 test_valuation_agent.py
"""

import asyncio

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.valuation_agent import ValuationAgent


# Shaped after the real AAPL output from the Phase 2 live test, with
# round numbers substituted for readability -- growth trend, sign
# conventions, and structure all match what was actually observed.
FAKE_FINANCIAL_DATA_DIVIDEND_PAYER = {
    "ticker": "TESTCO",
    "company_profile": {
        "ticker": "TESTCO",
        "long_name": "Test Company Inc.",
        "current_price": 300.0,
        "market_cap": 4_500_000_000_000,
        "beta": 1.1,
        "shares_outstanding": 15_000_000_000,
        "total_debt": 85_000_000_000,
        "total_cash": 68_000_000_000,
    },
    "cash_flow": {
        "operating_cash_flow_by_year": {
            "2022": 122_000_000_000,
            "2023": 110_000_000_000,
            "2024": 118_000_000_000,
            "2025": 111_000_000_000,
        },
        "capital_expenditure_by_year": {
            "2022": -10_700_000_000,
            "2023": -10_900_000_000,
            "2024": -9_400_000_000,
            "2025": -12_700_000_000,
        },
    },
    "price_history": {"ticker": "TESTCO", "latest_close": 300.0, "close_by_date": {}},
    "dividend_history": {
        "ticker": "TESTCO",
        "annual_dividends_per_share": {
            "2022": 0.91,
            "2023": 0.95,
            "2024": 0.99,
            "2025": 1.03,
            "2026": 0.53,  # deliberately partial-year, matching the real quirk found in Phase 2
        },
    },
    "dividend_history_error": None,
}

FAKE_FINANCIAL_DATA_NO_DIVIDEND = {
    **FAKE_FINANCIAL_DATA_DIVIDEND_PAYER,
    "dividend_history": None,
    "dividend_history_error": "No dividend history found for 'TESTCO'.",
}

FAKE_FINANCIAL_DATA_MISSING_BETA = {
    **FAKE_FINANCIAL_DATA_DIVIDEND_PAYER,
    "company_profile": {**FAKE_FINANCIAL_DATA_DIVIDEND_PAYER["company_profile"], "beta": None},
}


async def _run_valuation(financial_data, financial_data_error=None):
    agent = ValuationAgent()
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="test",
        user_id="u",
        state={"financial_data": financial_data, "financial_data_error": financial_data_error},
    )
    runner = Runner(agent=agent, app_name="test", session_service=session_service)

    async for _ in runner.run_async(
        user_id="u",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text="value it")]),
    ):
        pass

    final_session = await session_service.get_session(app_name="test", user_id="u", session_id=session.id)
    return final_session.state


def test_full_valuation_with_dividend_payer():
    state = asyncio.run(_run_valuation(FAKE_FINANCIAL_DATA_DIVIDEND_PAYER))

    assert state.get("valuation_result_error") is None, f"Unexpected error: {state.get('valuation_result_error')}"
    result = state["valuation_result"]

    # Sanity checks -- these are DERIVED numbers (growth-projected FCFF,
    # not the hand-verified fixed inputs from test_valuation.py), so we
    # check for sane ranges and internal consistency, not exact hand-calc.
    assert result["dcf"]["value_per_share"] > 0, "DCF per-share value should be positive"
    assert 0 < result["wacc"]["wacc"] < 0.3, f"WACC out of sane range: {result['wacc']['wacc']}"
    assert result["ddm"] is not None, "DDM should have run for a dividend-paying company"
    assert result["ddm"]["value_per_share"] > 0

    # Confirm the partial-year 2026 dividend was correctly EXCLUDED from
    # growth estimation (this guards the fix made in Phase 3 planning)
    assert result["ddm"]["historical_dividend_growth_rate"] > 0, (
        "Growth rate should be positive based on 2022-2025 clean trend; "
        "if this is wildly off, the partial-year 2026 figure may have "
        "leaked into the growth calculation."
    )

    print("test_full_valuation_with_dividend_payer PASSED")
    print(f"  DCF value/share: {result['dcf']['value_per_share']:.2f}")
    print(f"  DDM value/share: {result['ddm']['value_per_share']:.2f}")
    print(f"  WACC: {result['wacc']['wacc']:.4f}")
    print(f"  Current market price: {result['current_market_price']}")


def test_ddm_skipped_for_non_dividend_payer():
    state = asyncio.run(_run_valuation(FAKE_FINANCIAL_DATA_NO_DIVIDEND))

    assert state.get("valuation_result_error") is None
    result = state["valuation_result"]
    assert result["ddm"] is None
    assert result["ddm_skipped_reason"] == "non_dividend_paying_or_no_dividend_data"
    assert result["dcf"]["value_per_share"] > 0  # DCF should still run fine
    print("test_ddm_skipped_for_non_dividend_payer PASSED")


def test_missing_beta_fails_loudly():
    state = asyncio.run(_run_valuation(FAKE_FINANCIAL_DATA_MISSING_BETA))

    assert state.get("valuation_result_error") is not None, (
        "Missing beta should cause an explicit, loud failure -- not a "
        "silent fallback to some default that a user might not notice."
    )
    assert state.get("valuation_result") is None
    print("test_missing_beta_fails_loudly PASSED")


def test_missing_upstream_data_fails_loudly():
    state = asyncio.run(_run_valuation(None, financial_data_error="some upstream error"))

    assert state.get("valuation_result_error") == "missing_upstream_financial_data"
    print("test_missing_upstream_data_fails_loudly PASSED")


if __name__ == "__main__":
    test_full_valuation_with_dividend_payer()
    test_ddm_skipped_for_non_dividend_payer()
    test_missing_beta_fails_loudly()
    test_missing_upstream_data_fails_loudly()
    print("\nAll ValuationAgent tests passed.")
