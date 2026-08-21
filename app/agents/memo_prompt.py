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
- 6-Month Return: {_fmt(pt.get('return_6m_pct'), '{:+.1f}', '%')}
- 1-Year Return: {_fmt(pt.get('return_1y_pct'), '{:+.1f}', '%')}
- 3-Year Return: {_fmt(pt.get('return_3y_pct'), '{:+.1f}', '%')}
- 5-Year Return: {_fmt(pt.get('return_5y_pct'), '{:+.1f}', '%')}
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
MEMORANDUM STRUCTURE & NARRATIVE STYLE REQUIREMENT:
Synthesize all the financial data above into an institutional-grade research memorandum.
Write each section as cohesive, flowing analytical prose paragraphs that explain the company's financial story, operational strengths, capital allocation, and risk profile. Do NOT format as dry bullet lists or raw metric dumps.

Structure with these exact markdown headings:
### Executive Summary & Market Position
### Financial Health & Debt Profile
### Profitability, Cash Flow & Per-Share Trends
### Valuation & Industry Context
### Risk Guardrails & Observations

STRICT FORMATTING RULES:
1. Write flowing narrative prose paragraphs under each heading (do NOT use bullet lists).
2. Do NOT output conversational thoughts, reasoning tokens, scratchpad reflections, word counts, or draft revisions.
3. Do NOT output phrases like "Word count", "Let's check", "Rough estimate", or "Now produce final answer".
4. Output ONLY the finalized memorandum starting directly with "### Executive Summary & Market Position".
"""
    return prompt


def clean_memo_text(memo_text: str) -> str:
    """Robustly cleans LLM reasoning artifacts, repeated drafts, and meta-commentary."""
    if not memo_text:
        return ""
        
    import re
    # Strip <think> tags
    text = re.sub(r"<think>.*?</think>", "", memo_text, flags=re.DOTALL)
    
    # If there is a transition marker like 'Now produce final answer' or 'Final Answer:', take text after it
    parts = re.split(r"(?:now produce final answer|final answer:?|final output:?|final memo:?)[\s\.:]*", text, flags=re.IGNORECASE)
    if len(parts) > 1 and len(parts[-1].strip()) > 50:
        text = parts[-1]
            
    # If the text has multiple occurrences of '### Executive Summary', take the last one (discard previous drafts)
    exec_matches = list(re.finditer(r"(?:###|\*\*1\.|\#\#|\#\s)?\s*Executive Summary", text, flags=re.IGNORECASE))
    if len(exec_matches) > 1:
        last_idx = exec_matches[-1].start()
        text = text[last_idx:]
    elif exec_matches and exec_matches[0].start() > 0:
        text = text[exec_matches[0].start():]

    # Filter out individual lines that look like meta reasoning
    clean_lines = []
    skip_patterns = [
        r"word count", r"rough estimate", r"check that we", r"make sure not to",
        r"let\'s count", r"now produce", r"thinking process", r"draft \d"
    ]
    for line in text.split("\n"):
        if any(re.search(pat, line, re.IGNORECASE) for pat in skip_patterns) and not line.strip().startswith("#"):
            continue
        clean_lines.append(line)
        
    text = "\n".join(clean_lines).strip()
    
    # Ensure it starts with heading
    heading_match = re.search(r"(###|\*\*1\.|\#\#|\#\s|Executive Summary)", text)
    if heading_match and heading_match.start() > 0:
        text = text[heading_match.start():]
        
    return text.strip()

