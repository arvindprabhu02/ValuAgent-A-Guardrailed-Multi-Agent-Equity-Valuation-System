"""
Critic / Guardrail Agent.

Design note: this is the agent whose entire job is to catch bad numbers
before they reach the Memo Writer / end user. It is rule-based, not
LLM-based, deliberately -- an LLM "critic" could itself hallucinate a
plausible-sounding but wrong critique. A fixed set of numeric checks is
slower to extend but cannot lie about what it found.

Checks implemented (each documented with WHY it matters financially,
not just what threshold it uses):

1. DCF vs market price divergence -- flags if the model's fair value
   differs from the current market price by more than a threshold,
   with no attempt to explain WHY (that's left to the memo/human;
   this agent's job is only to flag, not to editorialize).

2. DDM reliability flag for low-payout-ratio companies -- Gordon
   Growth DDM systematically undervalues companies that return capital
   via buybacks rather than dividends (this was observed directly during
   Phase 3 testing: DDM valued a mega-cap tech company at ~5% of its
   DCF value). Rather than hide this, the Critic Agent flags it
   explicitly so the memo doesn't present DDM as equally reliable to DCF
   for such companies.

3. Terminal value weight check -- if the terminal value makes up an
   unusually large share of total enterprise value, the valuation is
   very sensitive to a single long-run assumption (terminal growth rate)
   and that sensitivity should be surfaced, not buried.

4. Negative/implausible growth check -- flags if the historical FCFF
   growth rate used was clamped at the min/max cap, meaning the
   historical trend was too extreme to use directly (a red flag for
   relying on the DCF output uncritically).
"""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from valuation.dcf import DcfInputs
from valuation.wacc import WaccInputs  # noqa: F401 (kept for type clarity in comments)


# Thresholds are prototype defaults, documented so they can be tuned or
# challenged rather than treated as ground truth.
MARKET_DIVERGENCE_WARNING_THRESHOLD = 0.30    # 30% away from market price
DDM_LOW_PAYOUT_RATIO_THRESHOLD = 0.15         # dividend yield on price below this = DDM unreliable
TERMINAL_VALUE_WEIGHT_WARNING_THRESHOLD = 0.80  # TV as share of enterprise value


class CriticAgent(BaseAgent):
    """
    Reads `valuation_result` and `sensitivity_result` from session state
    and runs a fixed set of numeric sanity checks, writing structured
    `flags` (a list of dicts, each with a `severity` and `message`) to
    session state as `critic_flags`. Never blocks the pipeline -- flags
    are informational, surfaced to the Memo Writer and the human reader,
    not a hard failure (a hard failure belongs to the agents upstream,
    when data itself is missing/invalid).
    """

    name: str = "critic_agent"
    description: str = (
        "Runs rule-based sanity checks on the DCF/DDM valuation output and "
        "flags anything a finance-literate reviewer would want to know about."
    )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        valuation_result = ctx.session.state.get("valuation_result")
        valuation_error = ctx.session.state.get("valuation_result_error")

        if valuation_error or not valuation_result:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=(
                        f"Cannot run critic checks: upstream valuation_result is missing "
                        f"or errored ({valuation_error!r})."
                    ))],
                ),
                actions=EventActions(
                    state_delta={"critic_flags_error": "missing_upstream_valuation_result"}
                ),
            )
            return

        flags = []

        ticker = valuation_result["ticker"]
        dcf = valuation_result["dcf"]
        ddm = valuation_result.get("ddm")
        market_price = valuation_result.get("current_market_price")
        assumptions = valuation_result["assumptions_used"]
        historical_growth = valuation_result["dcf_historical_fcff_growth_rate_used"]

        # --- Check 1: DCF vs market price divergence ---
        if market_price:
            dcf_divergence = (dcf["value_per_share"] - market_price) / market_price
            if abs(dcf_divergence) > MARKET_DIVERGENCE_WARNING_THRESHOLD:
                direction = "below" if dcf_divergence < 0 else "above"
                flags.append({
                    "severity": "warning",
                    "check": "dcf_market_divergence",
                    "message": (
                        f"DCF fair value (${dcf['value_per_share']:.2f}) is "
                        f"{abs(dcf_divergence):.0%} {direction} the current market price "
                        f"(${market_price:.2f}). This does not necessarily mean the model "
                        f"is wrong -- it may mean the market is pricing in growth, risk, "
                        f"or intangibles this DCF's assumptions don't capture. Treat as a "
                        f"prompt to review assumptions, not as a verdict."
                    ),
                })

        # --- Check 2: DDM reliability for low-payout-ratio companies ---
        if ddm and market_price:
            implied_dividend_yield = ddm["next_year_dividend"] / market_price
            if implied_dividend_yield < DDM_LOW_PAYOUT_RATIO_THRESHOLD * 0.1:
                # Using a stricter sub-threshold here since dividend yields
                # are typically single-digit percentages, not directly
                # comparable to the 15% divergence threshold used above.
                flags.append({
                    "severity": "warning",
                    "check": "ddm_low_payout_ratio",
                    "message": (
                        f"{ticker}'s implied dividend yield is only "
                        f"{implied_dividend_yield:.2%}. Gordon Growth DDM values the "
                        f"dividend stream only, so for companies that return capital "
                        f"primarily via buybacks or reinvestment rather than dividends, "
                        f"DDM will systematically understate fair value. DCF should be "
                        f"treated as the primary estimate here, not DDM."
                    ),
                })
        elif valuation_result.get("ddm_skipped_reason") == "non_dividend_paying_or_no_dividend_data":
            flags.append({
                "severity": "info",
                "check": "ddm_not_applicable",
                "message": f"{ticker} pays no dividends (or dividend data was unavailable); DDM was not run.",
            })

        # --- Check 3: Terminal value weight ---
        pv_fcff_total = sum(dcf["pv_fcff_by_year"])
        pv_terminal = dcf["pv_terminal_value"]
        enterprise_value = dcf["enterprise_value"]
        if enterprise_value > 0:
            tv_weight = pv_terminal / enterprise_value
            if tv_weight > TERMINAL_VALUE_WEIGHT_WARNING_THRESHOLD:
                flags.append({
                    "severity": "warning",
                    "check": "terminal_value_concentration",
                    "message": (
                        f"The terminal value makes up {tv_weight:.0%} of total enterprise "
                        f"value for {ticker}. This means the valuation is highly sensitive "
                        f"to the single terminal growth rate assumption "
                        f"({assumptions['terminal_growth_rate']:.2%}) -- see the sensitivity "
                        f"grid before treating the point estimate as precise."
                    ),
                })

        # --- Check 4: Growth rate was clamped ---
        if historical_growth in (assumptions["min_growth_cap"], assumptions["max_growth_cap"]):
            flags.append({
                "severity": "info",
                "check": "growth_rate_clamped",
                "message": (
                    f"The historical FCFF growth rate for {ticker} was clamped to "
                    f"{historical_growth:.2%} (the configured cap), meaning the raw "
                    f"historical trend was more extreme than this. The FCFF projection "
                    f"is therefore more conservative than a naive extrapolation would be."
                ),
            })

        summary = (
            f"Critic checks complete for {ticker}: {len(flags)} flag(s) raised "
            f"({sum(1 for f in flags if f['severity'] == 'warning')} warning, "
            f"{sum(1 for f in flags if f['severity'] == 'info')} info)."
        )

        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text=summary)]),
            actions=EventActions(
                state_delta={"critic_flags": flags, "critic_flags_error": None}
            ),
        )
