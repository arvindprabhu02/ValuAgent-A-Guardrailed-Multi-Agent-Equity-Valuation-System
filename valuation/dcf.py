"""
Discounted Cash Flow (DCF) valuation — Free Cash Flow to Firm (FCFF) approach.

Design note: this module does ONLY arithmetic. It never calls an LLM and
never makes a judgment call about whether an assumption is "reasonable" —
that job belongs to the Critic/Guardrail agent upstream. Keeping this
module dumb-but-correct is what lets the rest of the pipeline trust its
output without re-deriving it.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class DcfInputs:
    fcff_projections: List[float]  # explicit FCFF forecast, e.g. 5 years, in currency units
    wacc: float                    # discount rate, as decimal (from wacc.py)
    terminal_growth_rate: float    # perpetual growth rate assumed after projection window
    net_debt: float                # total debt - cash & equivalents
    shares_outstanding: float


def present_value(cash_flow: float, rate: float, period: int) -> float:
    """PV = CF / (1 + r)^t"""
    return cash_flow / ((1 + rate) ** period)


def terminal_value_gordon(final_year_fcff: float, wacc: float, terminal_growth: float) -> float:
    """
    Gordon Growth terminal value, applied at the END of the explicit
    projection window:

        TV_n = FCFF_n * (1 + g) / (WACC - g)

    Guardrail: WACC must exceed terminal growth, or the model is
    economically invalid (implies infinite/negative value).
    """
    if wacc <= terminal_growth:
        raise ValueError(
            f"WACC ({wacc:.4f}) must be greater than terminal growth rate "
            f"({terminal_growth:.4f}) for Gordon Growth terminal value to be valid."
        )
    return final_year_fcff * (1 + terminal_growth) / (wacc - terminal_growth)


def run_dcf(inputs: DcfInputs) -> dict:
    """
    Full DCF walk:
      1. PV of each explicit-period FCFF
      2. Terminal value at end of explicit period, discounted back to today
      3. Enterprise Value = sum of PVs + PV(terminal value)
      4. Equity Value = Enterprise Value - Net Debt
      5. Value per share = Equity Value / Shares Outstanding

    Returns a dict with every intermediate step, not just the final number —
    this is the artifact the Critic Agent and the Memo Writer Agent both
    read from directly.
    """
    n = len(inputs.fcff_projections)
    if n == 0:
        raise ValueError("fcff_projections must contain at least one year.")

    pv_fcff = [
        present_value(cf, inputs.wacc, t)
        for t, cf in enumerate(inputs.fcff_projections, start=1)
    ]

    tv = terminal_value_gordon(
        final_year_fcff=inputs.fcff_projections[-1],
        wacc=inputs.wacc,
        terminal_growth=inputs.terminal_growth_rate,
    )
    pv_terminal_value = present_value(tv, inputs.wacc, n)

    enterprise_value = sum(pv_fcff) + pv_terminal_value
    equity_value = enterprise_value - inputs.net_debt

    if inputs.shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive.")
    value_per_share = equity_value / inputs.shares_outstanding

    return {
        "pv_fcff_by_year": pv_fcff,
        "terminal_value_undiscounted": tv,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "value_per_share": value_per_share,
        "wacc_used": inputs.wacc,
        "terminal_growth_used": inputs.terminal_growth_rate,
    }
