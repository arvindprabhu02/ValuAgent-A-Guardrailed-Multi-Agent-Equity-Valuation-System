"""
Sensitivity Agent.

Design note: deliberately the thinnest agent in the pipeline. It adds NO
new valuation logic -- it re-runs the already-tested DCF function
(via valuation/sensitivity.py's wacc_growth_grid) across a small grid of
WACC/terminal-growth assumptions, using the EXACT SAME inputs the
Valuation Agent already used (persisted as `dcf_inputs_used`). This
means there is no way for this agent to introduce a valuation
discrepancy that wasn't already possible in the Valuation Agent --
one trusted formula, reused, not a second implementation that could drift.

Not an LLM agent, for the same reason as DataRetrievalAgent and
ValuationAgent: building a sensitivity grid is arithmetic, not judgment.
"""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from valuation.dcf import DcfInputs
from valuation.sensitivity import wacc_growth_grid


# Default grid deltas: +-1% and +-2% on both WACC and terminal growth.
# Kept small and symmetric for a prototype -- a production system might
# let the user configure this range.
DEFAULT_WACC_DELTAS = [-0.02, -0.01, 0.0, 0.01, 0.02]
DEFAULT_GROWTH_DELTAS = [-0.01, 0.0, 0.01]


class SensitivityAgent(BaseAgent):
    """
    Reads `valuation_result.dcf_inputs_used` from session state (written by
    ValuationAgent) and produces a WACC x terminal-growth sensitivity grid,
    written to session state as `sensitivity_result`.
    """

    name: str = "sensitivity_agent"
    description: str = (
        "Builds a WACC x terminal growth sensitivity grid by re-running the "
        "already-validated DCF function across a range of assumptions."
    )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        valuation_result = ctx.session.state.get("valuation_result")
        upstream_error = ctx.session.state.get("valuation_result_error")

        if upstream_error or not valuation_result:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=(
                        f"Cannot run sensitivity analysis: upstream valuation_result is "
                        f"missing or errored ({upstream_error!r}). Run ValuationAgent first."
                    ))],
                ),
                actions=EventActions(
                    state_delta={"sensitivity_result_error": "missing_upstream_valuation_result"}
                ),
            )
            return

        try:
            inputs_dict = valuation_result["dcf_inputs_used"]
            base_inputs = DcfInputs(
                fcff_projections=inputs_dict["fcff_projections"],
                wacc=inputs_dict["wacc"],
                terminal_growth_rate=inputs_dict["terminal_growth_rate"],
                net_debt=inputs_dict["net_debt"],
                shares_outstanding=inputs_dict["shares_outstanding"],
            )

            grid_result = wacc_growth_grid(
                base_inputs=base_inputs,
                wacc_deltas=DEFAULT_WACC_DELTAS,
                growth_deltas=DEFAULT_GROWTH_DELTAS,
            )

            ticker = valuation_result["ticker"]
            summary = (
                f"Sensitivity grid complete for {ticker}: value/share ranges from "
                f"{min(v for row in grid_result['grid'] for v in row if v is not None):.2f} to "
                f"{max(v for row in grid_result['grid'] for v in row if v is not None):.2f} "
                f"across the tested WACC/growth assumptions."
            )

            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=summary)]),
                actions=EventActions(
                    state_delta={
                        "sensitivity_result": grid_result,
                        "sensitivity_result_error": None,
                    }
                ),
            )

        except Exception as exc:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"Sensitivity analysis failed: {exc}")],
                ),
                actions=EventActions(
                    state_delta={"sensitivity_result_error": str(exc)}
                ),
            )
