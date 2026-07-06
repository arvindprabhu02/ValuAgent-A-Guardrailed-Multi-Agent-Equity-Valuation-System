"""
Weighted Average Cost of Capital (WACC) calculation.

WACC is the discount rate used in DCF to bring future free cash flows
to present value. It blends the cost of equity and after-tax cost of debt,
weighted by their share of total capital.

This module is intentionally pure Python / numeric only — no LLM calls,
no external API calls. It is the "trust anchor" of ValuAgent: every number
here should be independently reproducible by hand or in a spreadsheet.
"""

from dataclasses import dataclass


@dataclass
class WaccInputs:
    risk_free_rate: float       # e.g. 10-year govt bond yield, as decimal (0.07 = 7%)
    beta: float                 # equity beta of the stock
    market_risk_premium: float  # expected market return - risk free rate, as decimal
    cost_of_debt: float         # pre-tax cost of debt, as decimal
    tax_rate: float             # effective/marginal corporate tax rate, as decimal
    market_value_equity: float  # market cap
    market_value_debt: float    # total debt (book value is an acceptable proxy)


def cost_of_equity_capm(risk_free_rate: float, beta: float, market_risk_premium: float) -> float:
    """
    CAPM: Re = Rf + beta * (Market Risk Premium)
    """
    return risk_free_rate + beta * market_risk_premium


def after_tax_cost_of_debt(cost_of_debt: float, tax_rate: float) -> float:
    """
    Interest is tax-deductible, so the effective cost of debt to the firm is lower
    than the stated/coupon rate.
    """
    return cost_of_debt * (1 - tax_rate)


def calculate_wacc(inputs: WaccInputs) -> dict:
    """
    WACC = (E/V) * Re + (D/V) * Rd * (1 - Tc)

    Returns a dict with the final WACC plus intermediate values, so the
    Critic/Guardrail agent (and a human reviewer) can inspect every step
    rather than trusting a single opaque number.
    """
    re = cost_of_equity_capm(inputs.risk_free_rate, inputs.beta, inputs.market_risk_premium)
    rd_after_tax = after_tax_cost_of_debt(inputs.cost_of_debt, inputs.tax_rate)

    total_value = inputs.market_value_equity + inputs.market_value_debt
    if total_value <= 0:
        raise ValueError("Total firm value (equity + debt) must be positive.")

    weight_equity = inputs.market_value_equity / total_value
    weight_debt = inputs.market_value_debt / total_value

    wacc = weight_equity * re + weight_debt * rd_after_tax

    return {
        "wacc": wacc,
        "cost_of_equity": re,
        "after_tax_cost_of_debt": rd_after_tax,
        "weight_equity": weight_equity,
        "weight_debt": weight_debt,
    }
