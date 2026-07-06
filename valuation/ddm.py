"""
Dividend Discount Model (DDM) valuation.

Includes:
  - Single-stage Gordon Growth Model (constant perpetual dividend growth)
  - Two-stage model (high-growth phase, then stable perpetual growth)

Same design rule as dcf.py: pure arithmetic, no LLM, every intermediate
value returned for inspection by the Critic Agent / Memo Writer Agent.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class GordonDdmInputs:
    next_year_dividend: float   # D1, expected dividend next year
    required_return: float      # cost of equity, as decimal
    perpetual_growth_rate: float  # g, constant forever


@dataclass
class TwoStageDdmInputs:
    dividend_projections: List[float]  # explicit dividend forecast (high-growth phase)
    required_return: float
    terminal_growth_rate: float        # stable growth rate after explicit phase


def gordon_growth_ddm(inputs: GordonDdmInputs) -> dict:
    """
    P0 = D1 / (r - g)

    Guardrail: r must exceed g, same economic constraint as the DCF
    terminal value formula (they are mathematically the same shape).
    """
    if inputs.required_return <= inputs.perpetual_growth_rate:
        raise ValueError(
            f"Required return ({inputs.required_return:.4f}) must exceed growth rate "
            f"({inputs.perpetual_growth_rate:.4f}) for Gordon Growth DDM to be valid."
        )
    value_per_share = inputs.next_year_dividend / (
        inputs.required_return - inputs.perpetual_growth_rate
    )
    return {
        "value_per_share": value_per_share,
        "next_year_dividend": inputs.next_year_dividend,
        "required_return_used": inputs.required_return,
        "growth_rate_used": inputs.perpetual_growth_rate,
    }


def two_stage_ddm(inputs: TwoStageDdmInputs) -> dict:
    """
    Phase 1: discount each explicitly-forecast dividend back to present.
    Phase 2: apply Gordon Growth to the dividend AFTER the explicit window,
             discount that terminal value back to present.

    P0 = sum_{t=1..n} D_t / (1+r)^t   +   TV_n / (1+r)^n
    where TV_n = D_n * (1 + g) / (r - g)
    """
    n = len(inputs.dividend_projections)
    if n == 0:
        raise ValueError("dividend_projections must contain at least one year.")
    if inputs.required_return <= inputs.terminal_growth_rate:
        raise ValueError(
            f"Required return ({inputs.required_return:.4f}) must exceed terminal growth "
            f"({inputs.terminal_growth_rate:.4f})."
        )

    pv_dividends = [
        div / ((1 + inputs.required_return) ** t)
        for t, div in enumerate(inputs.dividend_projections, start=1)
    ]

    terminal_dividend = inputs.dividend_projections[-1] * (1 + inputs.terminal_growth_rate)
    terminal_value = terminal_dividend / (inputs.required_return - inputs.terminal_growth_rate)
    pv_terminal_value = terminal_value / ((1 + inputs.required_return) ** n)

    value_per_share = sum(pv_dividends) + pv_terminal_value

    return {
        "pv_dividends_by_year": pv_dividends,
        "terminal_value_undiscounted": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "value_per_share": value_per_share,
        "required_return_used": inputs.required_return,
        "terminal_growth_used": inputs.terminal_growth_rate,
    }
