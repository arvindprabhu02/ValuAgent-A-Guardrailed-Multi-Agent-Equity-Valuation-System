"""
Tests for CriticAgent, using realistic valuation_result shapes -- including
the ACTUAL numbers observed from test_valuation_agent.py's dividend-payer
case (DCF=67.15, DDM=14.31, market_price=300), which we already know
should trigger the market-divergence flag and the low-payout DDM flag.

Run with: python3 test_critic_agent.py
"""

import asyncio

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.critic_agent import CriticAgent


# Mirrors the real output observed from ValuationAgent's dividend-payer
# test case: DCF undervalues vs. market, DDM is far lower still (low
# payout ratio case).
VALUATION_RESULT_TRIGGERING_FLAGS = {
    "ticker": "TESTCO",
    "dcf": {
        "value_per_share": 67.15,
        "pv_fcff_by_year": [20.0, 19.0, 18.0, 17.0, 16.0],
        "pv_terminal_value": 900.0,
        "enterprise_value": 990.0,
    },
    "ddm": {
        "value_per_share": 14.31,
        "next_year_dividend": 1.06,
    },
    "ddm_skipped_reason": None,
    "current_market_price": 300.0,
    "assumptions_used": {
        "terminal_growth_rate": 0.025,
        "min_growth_cap": -0.20,
        "max_growth_cap": 0.20,
    },
    "dcf_historical_fcff_growth_rate_used": -0.03,  # not clamped, within range
}

VALUATION_RESULT_CLEAN = {
    "ticker": "CLEANCO",
    "dcf": {
        "value_per_share": 105.0,
        "pv_fcff_by_year": [20.0, 21.0, 22.0, 23.0, 24.0],
        "pv_terminal_value": 60.0,   # low terminal value weight
        "enterprise_value": 170.0,
    },
    "ddm": None,
    "ddm_skipped_reason": "non_dividend_paying_or_no_dividend_data",
    "current_market_price": 100.0,   # only ~5% divergence, should NOT flag
    "assumptions_used": {
        "terminal_growth_rate": 0.025,
        "min_growth_cap": -0.20,
        "max_growth_cap": 0.20,
    },
    "dcf_historical_fcff_growth_rate_used": 0.08,  # not clamped
}

VALUATION_RESULT_CLAMPED_GROWTH = {
    **VALUATION_RESULT_CLEAN,
    "dcf_historical_fcff_growth_rate_used": 0.20,  # exactly at max_growth_cap
}


async def _run_critic(valuation_result, valuation_result_error=None):
    agent = CriticAgent()
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="test",
        user_id="u",
        state={"valuation_result": valuation_result, "valuation_result_error": valuation_result_error},
    )
    runner = Runner(agent=agent, app_name="test", session_service=session_service)

    async for _ in runner.run_async(
        user_id="u",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text="critique")]),
    ):
        pass

    final_session = await session_service.get_session(app_name="test", user_id="u", session_id=session.id)
    return final_session.state


def test_flags_fire_for_diverging_valuation():
    state = asyncio.run(_run_critic(VALUATION_RESULT_TRIGGERING_FLAGS))
    flags = state["critic_flags"]
    checks_fired = {f["check"] for f in flags}

    assert "dcf_market_divergence" in checks_fired, "Should flag ~78% DCF-vs-market divergence"
    assert "ddm_low_payout_ratio" in checks_fired, "Should flag DDM unreliability for low payout ratio"
    assert "terminal_value_concentration" in checks_fired, "Should flag TV = 91% of enterprise value"

    print("test_flags_fire_for_diverging_valuation PASSED")
    for f in flags:
        print(f"  [{f['severity']}] {f['check']}")


def test_no_spurious_flags_for_clean_valuation():
    state = asyncio.run(_run_critic(VALUATION_RESULT_CLEAN))
    flags = state["critic_flags"]
    checks_fired = {f["check"] for f in flags}

    assert "dcf_market_divergence" not in checks_fired, "5% divergence should NOT trigger a warning"
    assert "terminal_value_concentration" not in checks_fired, "35% TV weight should NOT trigger a warning"
    assert "ddm_not_applicable" in checks_fired, "Should note DDM wasn't run for a non-dividend payer"

    print("test_no_spurious_flags_for_clean_valuation PASSED")


def test_clamped_growth_rate_is_flagged():
    state = asyncio.run(_run_critic(VALUATION_RESULT_CLAMPED_GROWTH))
    flags = state["critic_flags"]
    checks_fired = {f["check"] for f in flags}

    assert "growth_rate_clamped" in checks_fired
    print("test_clamped_growth_rate_is_flagged PASSED")


def test_missing_upstream_fails_loudly():
    state = asyncio.run(_run_critic(None, valuation_result_error="some error"))
    assert state.get("critic_flags_error") == "missing_upstream_valuation_result"
    print("test_missing_upstream_fails_loudly PASSED")


if __name__ == "__main__":
    test_flags_fire_for_diverging_valuation()
    test_no_spurious_flags_for_clean_valuation()
    test_clamped_growth_rate_is_flagged()
    test_missing_upstream_fails_loudly()
    print("\nAll CriticAgent tests passed.")
