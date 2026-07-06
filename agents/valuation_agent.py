"""
Valuation Agent.

Design note: like the Data Retrieval Agent, this is NOT an LLM agent.
Running a DCF/DDM calculation is pure arithmetic with no judgment
involved once the inputs are chosen -- exactly the kind of task an LLM
should never be trusted with (see project-level design principle: LLMs
narrate, they don't calculate). This agent is a thin ADK wrapper around
the already-tested valuation/ functions from Phase 1.

What this agent DOES have to decide (and must document transparently,
since these are real judgment calls a finance-literate reviewer will
scrutinize):

1. How to derive FCFF projections from historical cash flow data
   (a growth-rate extrapolation, capped to avoid nonsensical long-run
   assumptions).
2. What macro assumptions to use for WACC (risk-free rate, market risk
   premium, cost of debt, tax rate) -- yfinance does not provide these
   directly, so documented, overridable defaults are used. This is a
   known simplification for a prototype and should be stated plainly in
   the README, not hidden.
3. Whether DDM is applicable at all (only if the company pays dividends).

Every assumption used is written into the output under `assumptions_used`
specifically so the Critic Agent and Memo Writer Agent (and a human
reviewer) can see exactly what was assumed, not just the final numbers.
"""

from typing import AsyncGenerator, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from valuation.wacc import WaccInputs, calculate_wacc
from valuation.dcf import DcfInputs, run_dcf
from valuation.ddm import GordonDdmInputs, gordon_growth_ddm


# Documented default macro assumptions. These are prototype-level defaults,
# not live market data -- a production system would fetch current risk-free
# rates and credit spreads. Flagged explicitly here (and in the README) so
# nobody mistakes these for fetched data.
DEFAULT_ASSUMPTIONS = {
    "risk_free_rate": 0.045,       # approx. US 10-year treasury yield, prototype default
    "market_risk_premium": 0.05,   # standard long-run equity risk premium estimate
    "cost_of_debt": 0.055,         # approximate investment-grade corporate borrowing rate
    "tax_rate": 0.21,              # US federal corporate tax rate
    "projection_years": 5,
    "min_growth_cap": -0.20,       # floor on extrapolated historical growth rate
    "max_growth_cap": 0.20,        # ceiling on extrapolated historical growth rate
    "terminal_growth_rate": 0.025,  # capped near long-run GDP growth, not extrapolated
}


def _compute_historical_fcff_by_year(cash_flow: dict) -> dict:
    """
    FCFF = Operating Cash Flow - Capital Expenditure.

    Note on sign convention: yfinance reports Capital Expenditure as a
    NEGATIVE number (it's an outflow). So the subtraction is implemented
    as addition here (ocf + capex), since capex is already signed
    negative. This was verified against real AAPL data during Phase 2
    testing: OCF=111,482M, CapEx=-12,715M -> FCFF=98,767M, which requires
    ocf + capex, not ocf - capex.
    """
    ocf_by_year = cash_flow["operating_cash_flow_by_year"]
    capex_by_year = cash_flow["capital_expenditure_by_year"]

    fcff_by_year = {}
    for year in ocf_by_year:
        if year in capex_by_year:
            fcff_by_year[year] = ocf_by_year[year] + capex_by_year[year]
    return fcff_by_year


def _estimate_growth_rate(values_by_year_desc: dict, min_cap: float, max_cap: float) -> float:
    """
    Estimates a CAGR from historical values (assumed passed in
    most-recent-year-first order, matching yfinance's convention),
    clamped to [min_cap, max_cap] to avoid extrapolating a noisy or
    extreme historical trend indefinitely.
    """
    years_sorted = sorted(values_by_year_desc.keys())  # ascending
    values_ascending = [values_by_year_desc[y] for y in years_sorted]

    if len(values_ascending) < 2:
        return 0.0  # not enough data to estimate a trend; caller should treat conservatively

    earliest, latest = values_ascending[0], values_ascending[-1]
    n_periods = len(values_ascending) - 1

    if earliest <= 0 or latest <= 0:
        # Growth rate undefined/meaningless for negative or zero base FCFF
        # (a real system might use a different valuation approach here;
        # for this prototype we fall back to 0% growth rate).
        return 0.0

    cagr = (latest / earliest) ** (1 / n_periods) - 1
    return max(min_cap, min(max_cap, cagr))


def _project_fcff(latest_fcff: float, growth_rate: float, years: int) -> list:
    return [latest_fcff * ((1 + growth_rate) ** t) for t in range(1, years + 1)]


class ValuationAgent(BaseAgent):
    """
    Reads `financial_data` from session state (written by
    DataRetrievalAgent), derives DCF and (if applicable) DDM valuations,
    and writes `valuation_result` to session state.

    On failure (e.g. missing/invalid upstream data), writes
    `valuation_result_error` instead.
    """

    name: str = "valuation_agent"
    description: str = (
        "Runs DCF and DDM valuation on financial_data already present in "
        "session state, using deterministic, pre-tested arithmetic."
    )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        financial_data = ctx.session.state.get("financial_data")
        upstream_error = ctx.session.state.get("financial_data_error")

        if upstream_error or not financial_data:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=(
                        f"Cannot run valuation: upstream financial_data is missing or "
                        f"errored ({upstream_error!r}). Run DataRetrievalAgent successfully first."
                    ))],
                ),
                actions=EventActions(
                    state_delta={"valuation_result_error": "missing_upstream_financial_data"}
                ),
            )
            return

        try:
            assumptions = dict(DEFAULT_ASSUMPTIONS)
            ticker = financial_data["ticker"]
            profile = financial_data["company_profile"]
            cash_flow = financial_data["cash_flow"]

            # --- WACC ---
            market_cap = profile.get("market_cap")
            total_debt = profile.get("total_debt") or 0.0
            beta = profile.get("beta")

            if market_cap is None or beta is None:
                raise ValueError(
                    f"Missing required fields for WACC calculation "
                    f"(market_cap={market_cap}, beta={beta}). "
                    f"Cannot value {ticker} without these."
                )

            wacc_result = calculate_wacc(WaccInputs(
                risk_free_rate=assumptions["risk_free_rate"],
                beta=beta,
                market_risk_premium=assumptions["market_risk_premium"],
                cost_of_debt=assumptions["cost_of_debt"],
                tax_rate=assumptions["tax_rate"],
                market_value_equity=market_cap,
                market_value_debt=total_debt,
            ))

            # --- DCF ---
            fcff_by_year = _compute_historical_fcff_by_year(cash_flow)
            if len(fcff_by_year) < 2:
                raise ValueError(
                    f"Not enough historical cash flow data to estimate a growth "
                    f"trend for {ticker} (need at least 2 years, got {len(fcff_by_year)})."
                )

            historical_growth_rate = _estimate_growth_rate(
                fcff_by_year, assumptions["min_growth_cap"], assumptions["max_growth_cap"]
            )

            most_recent_year = max(fcff_by_year.keys())
            latest_fcff = fcff_by_year[most_recent_year]

            projected_fcff = _project_fcff(
                latest_fcff, historical_growth_rate, assumptions["projection_years"]
            )

            total_cash = profile.get("total_cash") or 0.0
            net_debt = total_debt - total_cash
            shares_outstanding = profile.get("shares_outstanding")

            if not shares_outstanding:
                raise ValueError(f"Missing shares_outstanding for {ticker}; cannot compute per-share value.")

            dcf_inputs_used = DcfInputs(
                fcff_projections=projected_fcff,
                wacc=wacc_result["wacc"],
                terminal_growth_rate=assumptions["terminal_growth_rate"],
                net_debt=net_debt,
                shares_outstanding=shares_outstanding,
            )
            dcf_result = run_dcf(dcf_inputs_used)

            # --- DDM (only if dividend data is available) ---
            ddm_result: Optional[dict] = None
            ddm_skipped_reason: Optional[str] = None

            dividend_history = financial_data.get("dividend_history")
            if dividend_history and dividend_history.get("annual_dividends_per_share"):
                div_by_year = dividend_history["annual_dividends_per_share"]

                # Exclude the current (likely partial) year from growth-rate
                # estimation -- discovered during live testing that the
                # current calendar year's dividend total is a partial-year
                # figure, not a full annual figure, which would understate
                # growth if included directly.
                years_sorted = sorted(div_by_year.keys())
                complete_years = {y: div_by_year[y] for y in years_sorted[:-1]} if len(years_sorted) > 1 else div_by_year

                if len(complete_years) >= 2:
                    div_growth_rate = _estimate_growth_rate(
                        complete_years, assumptions["min_growth_cap"], assumptions["max_growth_cap"]
                    )
                    most_recent_complete_year = max(complete_years.keys())
                    last_full_year_dividend = complete_years[most_recent_complete_year]
                    next_year_dividend = last_full_year_dividend * (1 + div_growth_rate)

                    ddm_result = gordon_growth_ddm(GordonDdmInputs(
                        next_year_dividend=next_year_dividend,
                        required_return=wacc_result["cost_of_equity"],
                        perpetual_growth_rate=assumptions["terminal_growth_rate"],
                    ))
                    ddm_result["historical_dividend_growth_rate"] = div_growth_rate
                else:
                    ddm_skipped_reason = "insufficient_complete_year_dividend_history"
            else:
                ddm_skipped_reason = "non_dividend_paying_or_no_dividend_data"

            valuation_result = {
                "ticker": ticker,
                "wacc": wacc_result,
                "dcf": dcf_result,
                "dcf_inputs_used": {
                    "fcff_projections": dcf_inputs_used.fcff_projections,
                    "wacc": dcf_inputs_used.wacc,
                    "terminal_growth_rate": dcf_inputs_used.terminal_growth_rate,
                    "net_debt": dcf_inputs_used.net_debt,
                    "shares_outstanding": dcf_inputs_used.shares_outstanding,
                },
                "dcf_historical_fcff_growth_rate_used": historical_growth_rate,
                "ddm": ddm_result,
                "ddm_skipped_reason": ddm_skipped_reason,
                "assumptions_used": assumptions,
                "current_market_price": profile.get("current_price"),
            }

            summary = (
                f"Valuation complete for {ticker}: "
                f"DCF value/share = {dcf_result['value_per_share']:.2f}, "
                f"WACC = {wacc_result['wacc']:.4f}."
            )
            if ddm_result:
                summary += f" DDM value/share = {ddm_result['value_per_share']:.2f}."
            else:
                summary += f" DDM skipped ({ddm_skipped_reason})."

            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=summary)]),
                actions=EventActions(
                    state_delta={
                        "valuation_result": valuation_result,
                        "valuation_result_error": None,
                    }
                ),
            )

        except Exception as exc:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"Valuation failed: {exc}")],
                ),
                actions=EventActions(
                    state_delta={"valuation_result_error": str(exc)}
                ),
            )
