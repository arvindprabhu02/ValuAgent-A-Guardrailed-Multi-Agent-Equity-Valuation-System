"""
Stage 2 Agent — Fundamental Analysis Agent.
"""

import logging
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions

logger = logging.getLogger(__name__)


class FundamentalAnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="fundamental_analysis_agent")

    async def _run_async_impl(self, ctx):
        logger.info("FundamentalAnalysisAgent computing metrics...")
        
        if ctx.session.state.get("financial_data_error"):
            ctx.session.state["fundamental_analysis_error"] = ctx.session.state["financial_data_error"]
            return

        fin = ctx.session.state.get("financial_data", {})
        profile = fin.get("company_profile", {})
        cf = fin.get("cash_flow", {})
        bs = ctx.session.state.get("balance_sheet_data", {})
        inc = ctx.session.state.get("income_statement_data", {})
        stats = ctx.session.state.get("key_statistics", {})
        price_trend = ctx.session.state.get("price_trend_data", {})
        insider = ctx.session.state.get("insider_transactions", [])

        def _latest(d):
            if not isinstance(d, dict) or not d:
                return None
            sorted_keys = sorted(d.keys(), reverse=True)
            return d[sorted_keys[0]]

        def _get_growth(d):
            if not isinstance(d, dict) or len(d) < 2:
                return None
            sorted_keys = sorted(d.keys(), reverse=True)
            latest_val = d[sorted_keys[0]]
            prev_val = d[sorted_keys[1]]
            if prev_val and prev_val != 0:
                return ((latest_val - prev_val) / abs(prev_val)) * 100.0
            return None

        # 1. Balance Sheet Health
        tot_assets = _latest(bs.get("total_assets"))
        tot_liab = _latest(bs.get("total_liabilities"))
        equity = _latest(bs.get("stockholders_equity"))
        curr_assets = _latest(bs.get("current_assets"))
        curr_liab = _latest(bs.get("current_liabilities"))
        cash = _latest(bs.get("cash_and_equivalents")) or profile.get("total_cash") or 0.0
        receivables = _latest(bs.get("receivables")) or 0.0
        tot_debt = _latest(bs.get("total_debt")) or profile.get("total_debt") or 0.0
        curr_debt = _latest(bs.get("current_debt")) or 0.0
        long_term_debt = _latest(bs.get("long_term_debt")) or 0.0
        ebitda = _latest(inc.get("ebitda"))

        current_ratio = stats.get("current_ratio") or ((curr_assets / curr_liab) if curr_assets and curr_liab else None)
        quick_ratio = stats.get("quick_ratio") or (((cash + receivables) / curr_liab) if curr_liab and curr_liab > 0 else None)
        debt_to_equity = (stats.get("debt_to_equity") / 100.0) if stats.get("debt_to_equity") is not None else ((tot_debt / equity) if equity and equity > 0 else None)
        net_debt = tot_debt - cash
        net_debt_to_ebitda = (net_debt / ebitda) if ebitda and ebitda > 0 else None

        interest_expense = abs(_latest(inc.get("interest_expense")) or 0.0)
        operating_income = _latest(inc.get("operating_income"))
        interest_coverage = (operating_income / interest_expense) if operating_income and interest_expense > 0 else None

        # 2. Profitability
        rev_dict = inc.get("total_revenue", {})
        rev_latest = _latest(rev_dict)
        revenue_growth_yoy = stats.get("revenue_growth") * 100.0 if stats.get("revenue_growth") is not None else _get_growth(rev_dict)
        gross_margin = stats.get("gross_margins") * 100.0 if stats.get("gross_margins") is not None else None
        operating_margin = stats.get("operating_margins") * 100.0 if stats.get("operating_margins") is not None else None
        net_margin = stats.get("profit_margins") * 100.0 if stats.get("profit_margins") is not None else None

        rd_spending = _latest(inc.get("research_development")) or 0.0
        rd_intensity = (rd_spending / rev_latest * 100.0) if rev_latest and rev_latest > 0 else 0.0

        # 3. Cash Flow Analysis
        ocf = _latest(cf.get("operating_cash_flow_by_year")) or 0.0
        capex = abs(_latest(cf.get("capital_expenditure_by_year")) or 0.0)
        fcf = ocf - capex
        market_cap = stats.get("market_cap") or profile.get("market_cap") or 0.0
        fcf_yield = (fcf / market_cap * 100.0) if market_cap and market_cap > 0 else None

        net_income = _latest(inc.get("net_income"))
        fcf_conversion = (fcf / net_income) if net_income and net_income > 0 else None
        reinvestment_ratio = (capex / ocf * 100.0) if ocf and ocf > 0 else None
        dividends_paid = abs(_latest(cf.get("dividends_paid_by_year")) or 0.0)
        buybacks = abs(_latest(cf.get("buybacks_by_year")) or 0.0)

        # 4. Per-Share Metrics
        diluted_eps = _latest(inc.get("diluted_eps")) or profile.get("trailing_pe")
        eps_dict = inc.get("diluted_eps", {})
        eps_growth_yoy = _get_growth(eps_dict)
        diluted_shares = _latest(inc.get("diluted_shares")) or profile.get("shares_outstanding") or 0.0

        fcf_per_share = (fcf / diluted_shares) if diluted_shares > 0 else None
        revenue_per_share = (rev_latest / diluted_shares) if rev_latest and diluted_shares > 0 else None
        book_value_per_share = (equity / diluted_shares) if equity and diluted_shares > 0 else None
        share_count_growth_yoy = _get_growth(inc.get("diluted_shares"))
        buyback_yield = (buybacks / market_cap * 100.0) if market_cap > 0 else 0.0
        sbc = abs(_latest(cf.get("stock_based_compensation_by_year")) or 0.0)
        dilution_pct = (sbc / market_cap * 100.0) if market_cap > 0 else 0.0

        # 5. Price Trend
        current_price = profile.get("current_price") or price_trend.get("latest_price")
        high_52w = stats.get("fifty_two_week_high")
        low_52w = stats.get("fifty_two_week_low")
        pct_from_52w_high = (((high_52w - current_price) / high_52w) * 100.0) if high_52w and current_price else None

        sma_50 = stats.get("fifty_day_average")
        sma_200 = stats.get("two_hundred_day_average")
        sma_signal = "BULLISH" if (current_price and sma_200 and current_price > sma_200) else "BEARISH"

        # 6. Moat & ROIC
        nopat = (operating_income * (1 - 0.21)) if operating_income else None
        invested_capital = (tot_debt + equity - cash) if (tot_debt is not None and equity is not None) else None
        roic = (stats.get("roic") * 100.0) if stats.get("roic") is not None else ((nopat / invested_capital * 100.0) if (nopat and invested_capital and invested_capital > 0) else None)
        roce = (stats.get("roce") * 100.0) if stats.get("roce") is not None else None

        # 7. Management & Governance
        insider_own = (stats.get("held_percent_insiders") * 100.0) if stats.get("held_percent_insiders") is not None else None
        inst_own = (stats.get("held_percent_institutions") * 100.0) if stats.get("held_percent_institutions") is not None else None

        insider_activity = "NEUTRAL"
        if insider:
            buys = sum(1 for t in insider if "buy" in str(t.get("Text", "")).lower() or "purchase" in str(t.get("Text", "")).lower())
            sells = sum(1 for t in insider if "sale" in str(t.get("Text", "")).lower() or "sell" in str(t.get("Text", "")).lower())
            if buys > sells:
                insider_activity = "NET BUYING"
            elif sells > buys:
                insider_activity = "NET SELLING"

        # 8. Dividend Analysis
        div_yield = (stats.get("dividend_yield") * 100.0) if stats.get("dividend_yield") is not None else None
        payout_ratio = (stats.get("payout_ratio") * 100.0) if stats.get("payout_ratio") is not None else None

        analysis = {
            "balance_sheet": {
                "current_ratio": current_ratio,
                "quick_ratio": quick_ratio,
                "debt_to_equity": debt_to_equity,
                "net_debt": net_debt,
                "interest_coverage": interest_coverage,
                "net_debt_to_ebitda": net_debt_to_ebitda,
                "debt_due_1y": curr_debt,
                "debt_due_2y_5y": long_term_debt,
            },
            "profitability": {
                "revenue_growth_yoy": revenue_growth_yoy,
                "gross_margin": gross_margin,
                "operating_margin": operating_margin,
                "net_margin": net_margin,
                "rd_intensity": rd_intensity,
            },
            "cash_flow": {
                "operating_cash_flow": ocf,
                "free_cash_flow": fcf,
                "fcf_yield": fcf_yield,
                "fcf_conversion": fcf_conversion,
                "reinvestment_ratio": reinvestment_ratio,
                "dividends_paid": dividends_paid,
                "buybacks": buybacks,
            },
            "per_share": {
                "diluted_eps": diluted_eps,
                "eps_growth_yoy": eps_growth_yoy,
                "fcf_per_share": fcf_per_share,
                "revenue_per_share": revenue_per_share,
                "book_value_per_share": book_value_per_share,
                "share_count_growth_yoy": share_count_growth_yoy,
                "buyback_yield": buyback_yield,
                "dilution_pct": dilution_pct,
            },
            "price_trend": {
                "current_price": current_price,
                "return_3m_pct": price_trend.get("return_3m_pct"),
                "return_6m_pct": price_trend.get("return_6m_pct"),
                "return_1y_pct": price_trend.get("return_1y_pct"),
                "return_3y_pct": price_trend.get("return_3y_pct"),
                "return_5y_pct": price_trend.get("return_5y_pct"),
                "avg_monthly_return_1y_pct": price_trend.get("avg_monthly_return_1y_pct"),
                "avg_monthly_return_5y_pct": price_trend.get("avg_monthly_return_5y_pct"),
                "high_52w": high_52w,
                "low_52w": low_52w,
                "pct_from_52w_high": pct_from_52w_high,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "sma_signal": sma_signal,
                "rsi_14": price_trend.get("rsi_14"),
                "beta": profile.get("beta"),
            },
            "valuation_multiples": {
                "trailing_pe": stats.get("trailing_pe") or profile.get("trailing_pe"),
                "forward_pe": stats.get("forward_pe") or profile.get("forward_pe"),
                "price_to_sales": stats.get("price_to_sales"),
                "price_to_book": stats.get("price_to_book"),
                "ev_to_ebitda": stats.get("ev_to_ebitda"),
                "peg_ratio": stats.get("peg_ratio"),
            },
            "moat": {
                "roic": roic,
                "roce": roce,
            },
            "governance": {
                "insider_ownership_pct": insider_own,
                "institutional_ownership_pct": inst_own,
                "recent_insider_activity": insider_activity,
            },
            "dividend": {
                "dividend_yield": div_yield,
                "payout_ratio": payout_ratio,
                "five_yr_avg_yield": stats.get("five_yr_avg_dividend_yield"),
            },
        }

        ctx.session.state["fundamental_analysis"] = analysis
        ctx.session.state["fundamental_analysis_error"] = None
        yield Event(author=self.name, text="Computed fundamental metrics.", actions=EventActions(state_delta={"fundamental_analysis": analysis, "fundamental_analysis_error": None}))
