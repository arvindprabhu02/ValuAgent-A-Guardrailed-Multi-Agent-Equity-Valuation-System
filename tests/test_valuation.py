"""
Hand-verifiable tests for the deterministic valuation core.

Each expected value below is computed independently, directly from the
textbook formula, inside the test itself — NOT copy-pasted from the
module's own output. This is deliberate: it catches bugs where the code
is internally consistent but implements the wrong formula.

Run with: python3 test_valuation.py
"""

from valuation import (
    WaccInputs, calculate_wacc,
    DcfInputs, run_dcf,
    GordonDdmInputs, gordon_growth_ddm,
    TwoStageDdmInputs, two_stage_ddm,
    wacc_growth_grid,
)


def approx(a, b, tol=1e-6):
    return abs(a - b) < tol


def test_wacc():
    inputs = WaccInputs(
        risk_free_rate=0.07,
        beta=1.2,
        market_risk_premium=0.05,
        cost_of_debt=0.09,
        tax_rate=0.25,
        market_value_equity=800,
        market_value_debt=200,
    )
    result = calculate_wacc(inputs)

    # Independent hand calc:
    # Re = 0.07 + 1.2*0.05 = 0.13
    # Rd_after_tax = 0.09*(1-0.25) = 0.0675
    # we = 800/1000 = 0.8, wd = 0.2
    # WACC = 0.8*0.13 + 0.2*0.0675 = 0.104 + 0.0135 = 0.1175
    expected_wacc = 0.1175
    assert approx(result["wacc"], expected_wacc), f"WACC mismatch: {result['wacc']} vs {expected_wacc}"
    assert approx(result["cost_of_equity"], 0.13)
    assert approx(result["after_tax_cost_of_debt"], 0.0675)
    print("test_wacc PASSED:", result)


def test_dcf():
    inputs = DcfInputs(
        fcff_projections=[100, 110, 121],  # 10% growth for 3 explicit years
        wacc=0.10,
        terminal_growth_rate=0.04,
        net_debt=200,
        shares_outstanding=100,
    )
    result = run_dcf(inputs)

    # Independent hand calc:
    pv1 = 100 / (1.10 ** 1)
    pv2 = 110 / (1.10 ** 2)
    pv3 = 121 / (1.10 ** 3)
    sum_pv = pv1 + pv2 + pv3

    tv = 121 * 1.04 / (0.10 - 0.04)
    pv_tv = tv / (1.10 ** 3)

    ev = sum_pv + pv_tv
    equity_value = ev - 200
    value_per_share = equity_value / 100

    assert approx(result["enterprise_value"], ev), f"EV mismatch: {result['enterprise_value']} vs {ev}"
    assert approx(result["equity_value"], equity_value)
    assert approx(result["value_per_share"], value_per_share)
    print(f"test_dcf PASSED: value_per_share = {result['value_per_share']:.4f} (expected {value_per_share:.4f})")


def test_dcf_invalid_wacc_raises():
    # WACC <= terminal growth should raise, not silently produce garbage
    inputs = DcfInputs(
        fcff_projections=[100],
        wacc=0.03,
        terminal_growth_rate=0.05,  # invalid: growth > WACC
        net_debt=0,
        shares_outstanding=10,
    )
    try:
        run_dcf(inputs)
        assert False, "Expected ValueError for WACC <= terminal growth, but none was raised"
    except ValueError:
        print("test_dcf_invalid_wacc_raises PASSED")


def test_gordon_ddm():
    inputs = GordonDdmInputs(
        next_year_dividend=5,
        required_return=0.11,
        perpetual_growth_rate=0.04,
    )
    result = gordon_growth_ddm(inputs)

    expected = 5 / (0.11 - 0.04)  # = 71.42857...
    assert approx(result["value_per_share"], expected), f"{result['value_per_share']} vs {expected}"
    print(f"test_gordon_ddm PASSED: value_per_share = {result['value_per_share']:.4f}")


def test_two_stage_ddm():
    inputs = TwoStageDdmInputs(
        dividend_projections=[5, 5.5, 6.05],  # 10% growth for 3 years
        required_return=0.11,
        terminal_growth_rate=0.04,
    )
    result = two_stage_ddm(inputs)

    pv1 = 5 / (1.11 ** 1)
    pv2 = 5.5 / (1.11 ** 2)
    pv3 = 6.05 / (1.11 ** 3)
    sum_pv = pv1 + pv2 + pv3

    terminal_dividend = 6.05 * 1.04
    tv = terminal_dividend / (0.11 - 0.04)
    pv_tv = tv / (1.11 ** 3)

    expected_value = sum_pv + pv_tv
    assert approx(result["value_per_share"], expected_value), \
        f"{result['value_per_share']} vs {expected_value}"
    print(f"test_two_stage_ddm PASSED: value_per_share = {result['value_per_share']:.4f}")


def test_sensitivity_grid():
    base = DcfInputs(
        fcff_projections=[100, 110, 121],
        wacc=0.10,
        terminal_growth_rate=0.04,
        net_debt=200,
        shares_outstanding=100,
    )
    grid_result = wacc_growth_grid(
        base_inputs=base,
        wacc_deltas=[-0.01, 0.0, 0.01],
        growth_deltas=[-0.01, 0.0, 0.01],
    )

    # Center cell (delta 0,0) should exactly match the base DCF run
    base_result = run_dcf(base)
    center_value = grid_result["grid"][1][1]  # row=wacc index1 (delta 0), col=growth index1 (delta 0)
    assert approx(center_value, round(base_result["value_per_share"], 2), tol=1e-2), \
        f"Center grid cell {center_value} should match base case {base_result['value_per_share']}"

    # Grid shape check
    assert len(grid_result["grid"]) == 3
    assert all(len(row) == 3 for row in grid_result["grid"])
    print("test_sensitivity_grid PASSED:", grid_result)


if __name__ == "__main__":
    test_wacc()
    test_dcf()
    test_dcf_invalid_wacc_raises()
    test_gordon_ddm()
    test_two_stage_ddm()
    test_sensitivity_grid()
    print("\nAll tests passed.")
