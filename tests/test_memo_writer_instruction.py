"""
Tests for the Memo Writer Agent's instruction-building logic ONLY.

This does NOT call any LLM -- it verifies that _build_instruction()
correctly reads session state and constructs a prompt containing the
right numbers, with no missing/garbled values. This is testable without
a Gemini API key. The actual LLM call must be verified separately with
test_memo_writer_agent_live.py, which DOES require a real API key and
was NOT run during this build.

_build_instruction only touches `ctx.state`, so a minimal duck-typed
stand-in object is used instead of a real ReadonlyContext (which
requires full ADK invocation machinery to construct).

Run with: python3 test_memo_writer_instruction.py
"""

from agents.memo_writer_agent import _build_instruction


class FakeReadonlyContext:
    """Minimal stand-in exposing only the `.state` attribute _build_instruction reads."""
    def __init__(self, state: dict):
        self.state = state


VALUATION_RESULT = {
    "ticker": "TESTCO",
    "dcf": {
        "value_per_share": 67.15,
        "enterprise_value": 990_000_000_000,
        "equity_value": 973_000_000_000,
    },
    "ddm": {
        "value_per_share": 14.31,
        "next_year_dividend": 1.06,
    },
    "wacc": {"wacc": 0.099, "cost_of_equity": 0.11},
    "current_market_price": 300.0,
    "assumptions_used": {"terminal_growth_rate": 0.025},
}

CRITIC_FLAGS = [
    {"severity": "warning", "check": "dcf_market_divergence", "message": "DCF is 78% below market price."},
    {"severity": "warning", "check": "ddm_low_payout_ratio", "message": "DDM unreliable for low payout ratio."},
]

SENSITIVITY_RESULT = {
    "wacc_values": [0.079, 0.089, 0.099, 0.109, 0.119],
    "growth_values": [0.015, 0.025, 0.035],
    "grid": [[100, 110, 125], [90, 99, 110], [80, 87, 95], [72, 78, 85], [65, 70, 76]],
}


def test_instruction_contains_all_key_numbers():
    ctx = FakeReadonlyContext({
        "valuation_result": VALUATION_RESULT,
        "critic_flags": CRITIC_FLAGS,
        "sensitivity_result": SENSITIVITY_RESULT,
    })
    instruction = _build_instruction(ctx)

    assert "TESTCO" in instruction
    assert "67.15" in instruction
    assert "14.31" in instruction
    assert "300.00" in instruction
    assert "9.90%" in instruction  # WACC formatted as percentage
    assert "dcf_market_divergence" not in instruction  # internal check names shouldn't leak, only messages
    assert "DCF is 78% below market price." in instruction
    assert "CRITICAL RULE" in instruction  # anti-hallucination instruction must be present

    print("test_instruction_contains_all_key_numbers PASSED")


def test_missing_valuation_produces_safe_fallback_instruction():
    ctx = FakeReadonlyContext({})
    instruction = _build_instruction(ctx)

    assert "Unable to generate memo" in instruction
    assert "TESTCO" not in instruction
    print("test_missing_valuation_produces_safe_fallback_instruction PASSED")


def test_ddm_not_applicable_case():
    valuation_no_ddm = {**VALUATION_RESULT, "ddm": None}
    ctx = FakeReadonlyContext({
        "valuation_result": valuation_no_ddm,
        "critic_flags": [{"severity": "info", "check": "ddm_not_applicable", "message": "No dividends paid."}],
        "sensitivity_result": None,
    })
    instruction = _build_instruction(ctx)

    assert "Not applicable" in instruction
    assert "No dividends paid." in instruction
    print("test_ddm_not_applicable_case PASSED")


if __name__ == "__main__":
    test_instruction_contains_all_key_numbers()
    test_missing_valuation_produces_safe_fallback_instruction()
    test_ddm_not_applicable_case()
    print("\nAll memo instruction-builder tests passed.")
