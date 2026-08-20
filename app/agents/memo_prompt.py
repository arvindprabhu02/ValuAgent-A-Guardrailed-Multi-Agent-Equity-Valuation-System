"""
Facts-Only Memo Prompt Builder.

Formats fundamental analysis, industry comparison, and critic guardrail flags
into a strict prompt for the Memo Writer Agent.
"""


def build_memo_prompt(state: dict) -> str:
    ticker = state.get("ticker", "UNKNOWN").upper()
    fa = state.get("fundamental_analysis", {})
    ind = state.get("industry_comparison", {})
    flags = state.get("critic_flags", [])

    bs = fa.get("balance_sheet", {})
    prof = fa.get("profitability", {})
    cf = fa.get("cash_flow", {})
    ps = fa.get("per_share", {})
    pt = fa.get("price_trend", {})
    vm = fa.get("valuation_multiples", {})
    moat = fa.get("moat", {})
    gov = fa.get("governance", {})
    div = fa.get("dividend", {})

    def _fmt(val, fmt_str="{:.2f}", suffix=""):
        if val is None:
            return "N/A"
        try:
            return fmt_str.format(val) + suffix
        except Exception:
            return str(val)

    flags_summary = "None flagged."
    if flags:
        flags_summary = "\n".join([f"- [{f['severity'].upper()}] {f['check']}: {f['message']}" for f in flags])

    prompt = f"""You are an elite institutional equity research analyst writing an Executive Equity Research Memorandum for ticker '{ticker}'.

CRITICAL ANTI-HALLUCINATION RULES:
1. Every number in your memo MUST come directly from the data below. Do not calculate, estimate, round differently, or invent ANY numeric value.
2. DO NOT predict future cash flows, target prices, or intrinsic fair values.
3. DO NOT give buy, sell, or hold recommendations. Present ONLY verified factual observations.

--------------------------------------------------------------------------------
FACTUAL DATA INPUTS FOR {ticker}
--------------------------------------------------------------------------------

1. PRICE & TECHNICAL TRENDS:
- Current Price: ${pt.get('current_price', 'N/A')}
- 3-Month Return: {_fmt(pt.get('return_3m_pct'), '{:+.1f}', '%')}
- 1-Year Return: {_fmt(pt.get('return_1y_pct'), '{:+.1f}', '%')}
- 52-Week High / Low: ${pt.get('high_52w', 'N/A')} / ${pt.get('low_52w', 'N/A')}
- % from 52-Week High: {_fmt(pt.get('pct_from_52w_high'), '-{:.1f}', '%')}
- SMA 50 / SMA 200: ${pt.get('sma_50', 'N/A')} / ${pt.get('sma_200', 'N/A')} (Signal: {pt.get('sma_signal', 'N/A')})
- RSI (14-day): {_fmt(pt.get('rsi_14'), '{:.1f}')}
- Beta: {_fmt(pt.get('beta'), '{:.2f}')}

2. INDUSTRY CONTEXT & BENCHMARKING:
- Sector / Industry: {ind.get('sector', 'N/A')} / {ind.get('industry', 'N/A')}
- Sector ETF Benchmark: {ind.get('sector_etf_ticker', 'N/A')}
- 1-Year Performance vs Sector: {ticker} {_fmt(ind.get('company_1y_return_pct'), '{:+.1f}', '%')} vs {ind.get('sector_etf_ticker')} {_fmt(ind.get('sector_etf_1y_return_pct'), '{:+.1f}', '%')}
- Outperformance Differential: {_fmt(ind.get('outperformance_pct'), '{:+.1f}', '%')}

3. BALANCE SHEET HEALTH & LIQUIDITY:
- Current Ratio: {_fmt(bs.get('current_ratio'), '{:.2f}')}
- Quick Ratio: {_fmt(bs.get('quick_ratio'), '{:.2f}')}
- Debt-to-Equity Ratio: {_fmt(bs.get('debt_to_equity'), '{:.2f}')}
- Net Debt: ${f"{bs.get('net_debt'):,.0f}" if isinstance(bs.get('net_debt'), (int, float)) else str(bs.get('net_debt'))}
- Interest Coverage: {_fmt(bs.get('interest_coverage'), '{:.1f}', 'x')}
- Net Debt / EBITDA: {_fmt(bs.get('net_debt_to_ebitda'), '{:.1f}', 'x')}
- Short-Term Debt (Due <1Y): ${_fmt(bs.get('debt_due_1y'))}
- Long-Term Debt (Due >1Y): ${_fmt(bs.get('debt_due_2y_5y'))}

4. PROFITABILITY & PER-SHARE METRICS:
- Revenue Growth (YoY): {_fmt(prof.get('revenue_growth_yoy'), '{:+.1f}', '%')}
- Gross Margin: {_fmt(prof.get('gross_margin'), '{:.1f}', '%')}
- Operating Margin: {_fmt(prof.get('operating_margin'), '{:.1f}', '%')}
- Net Profit Margin: {_fmt(prof.get('net_margin'), '{:.1f}', '%')}
- R&D Intensity: {_fmt(prof.get('rd_intensity'), '{:.1f}', '%')}
- Diluted EPS: ${ps.get('diluted_eps', 'N/A')}
- EPS Growth (YoY): {_fmt(ps.get('eps_growth_yoy'), '{:+.1f}', '%')}
- FCF per Share: ${_fmt(ps.get('fcf_per_share'), '{:.2f}')}
- Revenue per Share: ${_fmt(ps.get('revenue_per_share'), '{:.2f}')}
- Book Value per Share: ${_fmt(ps.get('book_value_per_share'), '{:.2f}')}
- Share Count Growth (YoY): {_fmt(ps.get('share_count_growth_yoy'), '{:+.1f}', '%')}
- Buyback Yield: {_fmt(ps.get('buyback_yield'), '{:.2f}', '%')}
- Dilution % (SBC / Market Cap): {_fmt(ps.get('dilution_pct'), '{:.2f}', '%')}

5. CASH FLOW QUALITY & CAPITAL ALLOCATION:
- Free Cash Flow: ${_fmt(cf.get('free_cash_flow'))}
- FCF Yield: {_fmt(cf.get('fcf_yield'), '{:.2f}', '%')}
- FCF Conversion (FCF / Net Income): {_fmt(cf.get('fcf_conversion'), '{:.2f}', 'x')}
- Reinvestment Ratio (CapEx / OCF): {_fmt(cf.get('reinvestment_ratio'), '{:.1f}', '%')}

6. VALUATION MULTIPLES:
- Trailing P/E: {_fmt(vm.get('trailing_pe'), '{:.1f}', 'x')}
- Forward P/E: {_fmt(vm.get('forward_pe'), '{:.1f}', 'x')}
- Price-to-Sales (P/S): {_fmt(vm.get('price_to_sales'), '{:.2f}', 'x')}
- Price-to-Book (P/B): {_fmt(vm.get('price_to_book'), '{:.2f}', 'x')}
- EV / EBITDA: {_fmt(vm.get('ev_to_ebitda'), '{:.1f}', 'x')}
- PEG Ratio: {_fmt(vm.get('peg_ratio'), '{:.2f}', 'x')}

7. MOAT, GOVERNANCE & DIVIDENDS:
- ROIC: {_fmt(moat.get('roic'), '{:.1f}', '%')}
- Insider Ownership %: {_fmt(gov.get('insider_ownership_pct'), '{:.2f}', '%')}
- Institutional Ownership %: {_fmt(gov.get('institutional_ownership_pct'), '{:.1f}', '%')}
- Recent Insider Activity: {gov.get('recent_insider_activity', 'N/A')}
- Dividend Yield: {_fmt(div.get('dividend_yield'), '{:.2f}', '%')}
- Dividend Payout Ratio: {_fmt(div.get('payout_ratio'), '{:.1f}', '%')}

8. CRITIC RISK GUARDRAIL FLAGS:
{flags_summary}

--------------------------------------------------------------------------------
MEMORANDUM STRUCTURE REQUIREMENT:
Synthesize the data into a professional 250-350 word research memo with clear markdown headings:
### Executive Summary & Market Position
### Financial Health & Debt Profile
### Profitability, Cash Flow & Per-Share Trends
### Valuation & Industry Context
### Risk Guardrails & Observations

Do NOT output conversational thoughts, reasoning tokens, or preamble. Start directly with the memo text.
"""
    return prompt
