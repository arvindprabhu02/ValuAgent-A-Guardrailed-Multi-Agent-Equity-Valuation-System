"""
Stage 4 Agent — Critic Agent (Guardrails).
"""

import logging
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="critic_agent")

    async def _run_async_impl(self, ctx):
        logger.info("CriticAgent evaluating 8 fact-based guardrail checks...")
        
        fa = ctx.session.state.get("fundamental_analysis", {})
        if not fa:
            ctx.session.state["critic_flags"] = []
            return

        bs = fa.get("balance_sheet", {})
        prof = fa.get("profitability", {})
        cf = fa.get("cash_flow", {})
        ps = fa.get("per_share", {})
        gov = fa.get("governance", {})
        div = fa.get("dividend", {})

        flags = []

        # 1. Liquidity Risk (Current Ratio < 1.0)
        cr = bs.get("current_ratio")
        if cr is not None and cr < 1.0:
            flags.append({
                "severity": "warning",
                "check": "Liquidity Risk",
                "message": f"Current ratio is {cr:.2f} (< 1.0). Short-term liabilities exceed current assets.",
            })

        # 2. High Leverage (Debt-to-Equity > 2.0)
        de = bs.get("debt_to_equity")
        if de is not None and de > 2.0:
            flags.append({
                "severity": "warning",
                "check": "High Leverage",
                "message": f"Debt-to-Equity ratio is {de:.2f} (> 2.0). High balance sheet financial leverage.",
            })

        # 3. Low Interest Coverage (< 3.0x)
        ic = bs.get("interest_coverage")
        if ic is not None and ic < 3.0:
            flags.append({
                "severity": "warning",
                "check": "Low Interest Coverage",
                "message": f"Interest coverage is {ic:.1f}x (< 3.0x). Operating earnings barely cover interest payments.",
            })

        # 4. Margin Deterioration (Net Margin < 5%)
        nm = prof.get("net_margin")
        if nm is not None and nm < 5.0:
            flags.append({
                "severity": "warning",
                "check": "Margin Deterioration",
                "message": f"Net profit margin is low at {nm:.1f}% (< 5.0%). Thin bottom-line margin buffer.",
            })

        # 5. Negative Free Cash Flow (FCF < 0)
        fcf = cf.get("free_cash_flow")
        if fcf is not None and fcf < 0:
            flags.append({
                "severity": "warning",
                "check": "Negative Free Cash Flow",
                "message": "Free Cash Flow is negative. Capital expenditures and operations exceed cash generated.",
            })

        # 6. Low Earnings Quality (FCF / Net Income < 0.5x)
        fcf_conv = cf.get("fcf_conversion")
        if fcf_conv is not None and fcf_conv < 0.5:
            flags.append({
                "severity": "info",
                "check": "Low Earnings Quality",
                "message": f"FCF Conversion is {fcf_conv:.2f}x (< 0.5x). Reported net income exceeds actual cash flow.",
            })

        # 7. Insider Selling Cluster
        activity = gov.get("recent_insider_activity")
        if activity == "NET SELLING":
            flags.append({
                "severity": "info",
                "check": "Insider Selling Cluster",
                "message": "Recent insider activity shows net selling in recent transactions.",
            })

        # 8. Dividend Unsustainability (Payout Ratio > 85%)
        payout = div.get("payout_ratio")
        if payout is not None and payout > 85.0:
            flags.append({
                "severity": "warning",
                "check": "Dividend Unsustainability Risk",
                "message": f"Dividend payout ratio is {payout:.1f}% (> 85.0%). High vulnerability to dividend cuts.",
            })

        # Quality of Growth Check: EPS Growth >> Revenue Growth
        eps_g = ps.get("eps_growth_yoy")
        rev_g = prof.get("revenue_growth_yoy")
        if eps_g is not None and rev_g is not None and eps_g > (rev_g + 15.0):
            flags.append({
                "severity": "info",
                "check": "Quality of Growth Divergence",
                "message": f"EPS growth (+{eps_g:.1f}%) significantly outpaces Revenue growth (+{rev_g:.1f}%). Growth may be driven by share buybacks or cost cutting.",
            })

        ctx.session.state["critic_flags"] = flags
        ctx.session.state["critic_flags_error"] = None
        yield Event(author=self.name, text=f"Evaluated {len(flags)} risk flags.", actions=EventActions(state_delta={"critic_flags": flags, "critic_flags_error": None}))
