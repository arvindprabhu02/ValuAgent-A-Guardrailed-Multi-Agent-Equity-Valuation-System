"""
Tests for SensitivityAgent. Runs the real Runner + real agent + real
underlying valuation/sensitivity.py functions -- no mocking needed here,
since this agent has no external dependencies (no network, no subprocess).

Run with: python3 test_sensitivity_agent.py
"""

import asyncio

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.sensitivity_agent import SensitivityAgent


FAKE_VALUATION_RESULT = {
    "ticker": "TESTCO",
    # value_per_share below is the ACTUAL run_dcf() output for the
    # dcf_inputs_used below (verified with valuation.dcf.run_dcf directly)
    # -- not a hand-typed guess. An earlier version of this test used a
    # fabricated mismatched value and incorrectly flagged the agent as
    # buggy when the agent's math was actually correct.
    "dcf": {"value_per_share": 87.33},
    "dcf_inputs_used": {
        "fcff_projections": [100_000_000_000, 102_000_000_000, 104_000_000_000, 106_000_000_000, 108_000_000_000],
        "wacc": 0.099,
        "terminal_growth_rate": 0.025,
        "net_debt": 17_000_000_000,
        "shares_outstanding": 15_000_000_000,
    },
}


async def _run_sensitivity(valuation_result, valuation_result_error=None):
    agent = SensitivityAgent()
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
        new_message=types.Content(role="user", parts=[types.Part(text="run sensitivity")]),
    ):
        pass

    final_session = await session_service.get_session(app_name="test", user_id="u", session_id=session.id)
    return final_session.state


def test_sensitivity_grid_matches_base_case_at_center():
    state = asyncio.run(_run_sensitivity(FAKE_VALUATION_RESULT))

    assert state.get("sensitivity_result_error") is None
    result = state["sensitivity_result"]

    # Center of the grid (delta 0, 0) should match the DCF's own reported
    # value/share almost exactly -- confirms the agent is reusing the
    # EXACT SAME inputs, not silently recomputing with different ones.
    wacc_center_idx = result["wacc_values"].index(FAKE_VALUATION_RESULT["dcf_inputs_used"]["wacc"])
    growth_center_idx = result["growth_values"].index(FAKE_VALUATION_RESULT["dcf_inputs_used"]["terminal_growth_rate"])
    center_value = result["grid"][wacc_center_idx][growth_center_idx]

    expected = FAKE_VALUATION_RESULT["dcf"]["value_per_share"]
    assert abs(center_value - expected) < 0.5, (
        f"Center grid cell {center_value} should closely match the base DCF "
        f"value {expected} -- large mismatch suggests inputs were not reused correctly."
    )

    # Grid shape sanity check
    assert len(result["grid"]) == 5   # 5 WACC deltas
    assert all(len(row) == 3 for row in result["grid"])  # 3 growth deltas

    print("test_sensitivity_grid_matches_base_case_at_center PASSED")
    print(f"  Center value/share: {center_value:.2f} (base DCF reported: {expected:.2f})")


def test_missing_upstream_fails_loudly():
    state = asyncio.run(_run_sensitivity(None, valuation_result_error="some upstream error"))
    assert state.get("sensitivity_result_error") == "missing_upstream_valuation_result"
    print("test_missing_upstream_fails_loudly PASSED")


if __name__ == "__main__":
    test_sensitivity_grid_matches_base_case_at_center()
    test_missing_upstream_fails_loudly()
    print("\nAll SensitivityAgent tests passed.")
