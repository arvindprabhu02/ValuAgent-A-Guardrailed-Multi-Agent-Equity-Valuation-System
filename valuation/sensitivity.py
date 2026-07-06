"""
Sensitivity analysis: shows how DCF value-per-share changes as WACC and
terminal growth rate are varied around the base case.

This is deliberately a thin wrapper around dcf.run_dcf — it doesn't
introduce new valuation logic, it just re-runs the trusted DCF function
across a grid of assumptions. This is the "Sensitivity Agent" in the
ADK pipeline; it depends on the Valuation Agent's logic and adds nothing
that could introduce a new class of bug.
"""

from typing import List
from .dcf import DcfInputs, run_dcf


def wacc_growth_grid(
    base_inputs: DcfInputs,
    wacc_deltas: List[float],
    growth_deltas: List[float],
) -> dict:
    """
    Build a 2D grid of value_per_share, varying WACC and terminal growth
    by the given deltas (as decimals, e.g. [-0.01, 0.0, 0.01]) around the
    base case values in base_inputs.

    Returns a dict shaped for easy tabular/markdown rendering:
        {
          "wacc_values": [...],
          "growth_values": [...],
          "grid": [[value_per_share, ...], ...]   # rows = wacc, cols = growth
        }
    Cells where WACC <= growth (economically invalid) are set to None
    rather than raising, so the grid renders cleanly with gaps.
    """
    wacc_values = [round(base_inputs.wacc + d, 6) for d in wacc_deltas]
    growth_values = [round(base_inputs.terminal_growth_rate + d, 6) for d in growth_deltas]

    grid = []
    for w in wacc_values:
        row = []
        for g in growth_values:
            if w <= g:
                row.append(None)
                continue
            scenario_inputs = DcfInputs(
                fcff_projections=base_inputs.fcff_projections,
                wacc=w,
                terminal_growth_rate=g,
                net_debt=base_inputs.net_debt,
                shares_outstanding=base_inputs.shares_outstanding,
            )
            result = run_dcf(scenario_inputs)
            row.append(round(result["value_per_share"], 2))
        grid.append(row)

    return {
        "wacc_values": wacc_values,
        "growth_values": growth_values,
        "grid": grid,
    }
