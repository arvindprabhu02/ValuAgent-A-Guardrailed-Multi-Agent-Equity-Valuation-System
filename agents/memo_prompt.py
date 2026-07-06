"""
Shared module for building the strict investment memo prompt.
"""

def build_memo_prompt(state: dict) -> str:
    """
    Builds the memo-writing prompt from a plain state dictionary.
    
    This function reads `valuation_result`, `sensitivity_result`, and
    `critic_flags` from state and builds the exact same strict,
    anti-hallucination prompt.
    """
    valuation = state.get("valuation_result")
    sensitivity = state.get("sensitivity_result")
    flags = state.get("critic_flags", [])

    if not valuation:
        return (
            "No valuation data is available in session state. "
            "Respond only with: 'Unable to generate memo: valuation data is missing.' "
            "Do not attempt to write a memo without this data."
        )

    ticker = valuation["ticker"]
    dcf = valuation["dcf"]
    ddm = valuation.get("ddm")
    market_price = valuation.get("current_market_price")
    wacc = valuation["wacc"]["wacc"]
    assumptions = valuation["assumptions_used"]

    flags_text = "\n".join(f"- [{f['severity'].upper()}] {f['message']}" for f in flags) or "None."

    sensitivity_text = "Not available."
    if sensitivity:
        sensitivity_text = (
            f"WACC range tested: {sensitivity['wacc_values']}\n"
            f"Terminal growth range tested: {sensitivity['growth_values']}\n"
            f"Resulting value/share grid (rows=WACC, columns=growth): {sensitivity['grid']}"
        )

    ddm_text = "Not applicable (see reason in flags)." if not ddm else (
        f"${ddm['value_per_share']:.2f} per share "
        f"(next year dividend assumed: ${ddm['next_year_dividend']:.2f}, "
        f"required return: {valuation['wacc']['cost_of_equity']:.2%})"
    )

    return f"""You are writing a short investment analysis memo for {ticker}.

CRITICAL RULE: Every number in your memo must come from the data below.
Do not calculate, estimate, round differently, or invent ANY numeric value
that is not explicitly given to you here. If you want to state a number
that isn't below, say the analysis doesn't cover that instead. Your job is
to explain and contextualize these already-computed numbers in clear
prose, not to do any math yourself.

--- COMPUTED VALUATION DATA (this is the complete and only source of numbers you may use) ---

Ticker: {ticker}
Current market price: ${market_price:.2f}
WACC used: {wacc:.2%}

DCF fair value: ${dcf['value_per_share']:.2f} per share
  - Enterprise value: ${dcf['enterprise_value']:,.0f}
  - Equity value: ${dcf['equity_value']:,.0f}
  - Terminal growth rate assumption: {assumptions['terminal_growth_rate']:.2%}

DDM fair value: {ddm_text}

Sensitivity analysis:
{sensitivity_text}

Critic/guardrail flags (things a reviewer should know about this valuation):
{flags_text}

--- END OF DATA ---

Write a concise investment memo (roughly 250-350 words) covering:
1. The bottom-line valuation conclusion (state both DCF and DDM figures if DDM is applicable)
2. How this compares to the current market price
3. Key assumptions and their limitations (reference the critic flags where relevant)
4. What the sensitivity analysis implies about confidence in the point estimate

Do not use hedging filler ("it's important to note that...") more than once.
Be direct about what this valuation can and cannot tell an investor."""
