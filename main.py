"""
ValuAgent Command-Line Entry Point & Web App Launcher.

Usage:
  python run_valuagent.py AAPL
  python run_valuagent.py --web
"""

import sys
import os
import asyncio
import logging
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from app.agents.orchestrator import root_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_valuagent")

APP_NAME = "valuagent"
USER_ID = "cli_user"


def _has_llm_api_key() -> bool:
    return bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GROQ_API_KEY")
    )


async def run_cli(ticker_symbol: str):
    print(f"\n==================================================")
    print(f"       ValuAgent — Equity Research Platform       ")
    print(f"==================================================\n")
    print(f"Analyzing ticker: {ticker_symbol.upper()}...")

    if not _has_llm_api_key():
        print("Notice: No LLM API key detected. Running deterministic analysis stages (1-4) only.\n")

    session_service = InMemorySessionService()
    session_id = f"cli_{ticker_symbol.upper()}"

    session = await session_service.create_session(
        session_id=session_id,
        app_name=APP_NAME,
        user_id=USER_ID,
        state={"ticker": ticker_symbol.upper()},
    )

    runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)
    input_content = Content(parts=[Part(text="Run Equity Research")])

    async for event in runner.run_async(session_id=session.id, user_id=USER_ID, new_message=input_content):
        actions = getattr(event, "actions", None)
        if actions and getattr(actions, "state_delta", None):
            session.state.update(actions.state_delta)

        author = getattr(event, "author", "agent")
        text = getattr(event, "text", "")
        if text:
            print(f"[{author}]: {text[:120]}..." if len(text) > 120 else f"[{author}]: {text}")

    final_session = await session_service.get_session(session_id=session.id, app_name=APP_NAME, user_id=USER_ID)
    state = final_session.state

    if state.get("financial_data_error"):
        print(f"\n[ERROR]: {state['financial_data_error']}")
        return

    fa = state.get("fundamental_analysis") or {}
    ind = state.get("industry_comparison") or {}
    flags = state.get("critic_flags") or []

    bs = fa.get("balance_sheet") or {}
    prof = fa.get("profitability") or {}
    ps = fa.get("per_share") or {}
    vm = fa.get("valuation_multiples") or {}
    pt = fa.get("price_trend") or {}

    print(f"\n==================================================")
    print(f"       EQUITY RESEARCH SUMMARY: {ticker_symbol.upper()}       ")
    print(f"==================================================")
    print(f"Current Price:     ${pt.get('current_price', 'N/A')}")
    print(f"1-Year Return:     {pt.get('return_1y_pct', 0.0):+.1f}%" if pt.get('return_1y_pct') is not None else "1-Year Return:     N/A")
    print(f"Industry:          {ind.get('sector', 'N/A')} ({ind.get('industry', 'N/A')})")
    print(f"vs Sector ({ind.get('sector_etf_ticker', 'N/A')}):  {ind.get('outperformance_pct', 0.0):+.1f}% outperformance" if ind.get('outperformance_pct') is not None else "vs Sector:         N/A")
    print(f"--------------------------------------------------")
    print(f"BALANCE SHEET & LIQUIDITY:")
    print(f"  Current Ratio:   {bs.get('current_ratio', 'N/A')}")
    print(f"  Debt-to-Equity:  {bs.get('debt_to_equity', 'N/A')}")
    print(f"  Net Debt/EBITDA: {bs.get('net_debt_to_ebitda', 'N/A')}x" if bs.get('net_debt_to_ebitda') is not None else "  Net Debt/EBITDA: N/A")
    print(f"--------------------------------------------------")
    print(f"PROFITABILITY & PER-SHARE:")
    print(f"  Revenue Growth:  {prof.get('revenue_growth_yoy', 0.0):+.1f}%" if prof.get('revenue_growth_yoy') is not None else "  Revenue Growth:  N/A")
    print(f"  Net Margin:      {prof.get('net_margin', 0.0):.1f}%" if prof.get('net_margin') is not None else "  Net Margin:      N/A")
    print(f"  Diluted EPS:     ${ps.get('diluted_eps', 'N/A')}")
    print(f"  FCF per Share:   ${ps.get('fcf_per_share', 'N/A')}")
    print(f"--------------------------------------------------")
    print(f"VALUATION MULTIPLES:")
    print(f"  Trailing P/E:    {vm.get('trailing_pe', 'N/A')}x" if vm.get('trailing_pe') is not None else "  Trailing P/E:    N/A")
    print(f"  Forward P/E:     {vm.get('forward_pe', 'N/A')}x" if vm.get('forward_pe') is not None else "  Forward P/E:     N/A")
    print(f"  P/S Ratio:       {vm.get('price_to_sales', 'N/A')}x" if vm.get('price_to_sales') is not None else "  P/S Ratio:       N/A")
    print(f"  EV/EBITDA:       {vm.get('ev_to_ebitda', 'N/A')}x" if vm.get('ev_to_ebitda') is not None else "  EV/EBITDA:       N/A")

    if flags:
        print(f"--------------------------------------------------")
        print(f"RISK GUARDRAIL FLAGS ({len(flags)}):")
        for f in flags:
            print(f"  - [{f['severity'].upper()}] {f['check']}: {f['message']}")

    memo = state.get("memo_text")
    if memo:
        print(f"\n==================================================")
        print(f"             RESEARCH MEMORANDUM                  ")
        print(f"==================================================\n")
        try:
            print(memo)
        except UnicodeEncodeError:
            print(memo.encode("ascii", "replace").decode("ascii"))

        out_file = f"{ticker_symbol.upper()}_valuation_memo.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(memo)
        print(f"\nSaved memo to {out_file}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        import uvicorn
        port = int(os.environ.get("PORT", 8080))
        print(f"Starting ValuAgent Web App on port {port}...")
        uvicorn.run("app.web.web_app:app", host="0.0.0.0", port=port, reload=False)
    elif len(sys.argv) > 1:
        ticker = sys.argv[1]
        asyncio.run(run_cli(ticker))
    else:
        print("Usage:")
        print("  python run_valuagent.py TICKER")
        print("  python run_valuagent.py --web")


if __name__ == "__main__":
    main()
