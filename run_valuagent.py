"""
ValuAgent CLI entrypoint.

Usage:
    python3 run_valuagent.py TICKER

Example:
    python3 run_valuagent.py AAPL

Requirements to run the FULL pipeline (all 5 agents, including the memo):
    - Internet access (for the MCP server's yfinance calls)
    - A Gemini API key set as GOOGLE_API_KEY or GEMINI_API_KEY

If no API key is set, this script still runs the four deterministic
agents (data retrieval, valuation, sensitivity, critic) and reports the
raw numbers -- it just skips the memo-writing step and says so clearly,
rather than crashing.
"""

import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


def _has_llm_api_key() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


async def run(ticker: str):
    session_service = InMemorySessionService()
    app_name = "valuagent_cli"
    user_id = "cli_user"

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={"ticker": ticker}
    )

    if _has_llm_api_key():
        from agents.orchestrator import root_agent
        agent = root_agent
        print(f"Running full ValuAgent pipeline (including memo) for {ticker}...\n")
    else:
        # Build the same pipeline minus the LLM-dependent memo step, so the
        # CLI still produces useful output without requiring an API key.
        from google.adk.agents import SequentialAgent
        from agents.data_retrieval_agent import DataRetrievalAgent
        from agents.valuation_agent import ValuationAgent
        from agents.sensitivity_agent import SensitivityAgent
        from agents.critic_agent import CriticAgent

        agent = SequentialAgent(
            name="valuagent_no_memo",
            sub_agents=[
                DataRetrievalAgent(), ValuationAgent(), SensitivityAgent(), CriticAgent(),
            ],
        )
        print(
            f"No GOOGLE_API_KEY / GEMINI_API_KEY found -- running the deterministic "
            f"stages only (no memo will be generated) for {ticker}...\n"
        )

    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=f"Value {ticker}")]),
    ):
        if event.content and event.content.parts and event.content.parts[0].text:
            print(f"[{event.author}] {event.content.parts[0].text}\n")

    final_session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session.id)
    state = final_session.state

    print("=" * 60)
    print(f"RESULTS FOR {ticker}")
    print("=" * 60)

    if state.get("financial_data_error"):
        print(f"FAILED at data retrieval: {state['financial_data_error']}")
        return
    if state.get("valuation_result_error"):
        print(f"FAILED at valuation: {state['valuation_result_error']}")
        return

    valuation = state["valuation_result"]
    print(f"Current market price: ${valuation['current_market_price']:.2f}")
    print(f"DCF fair value:       ${valuation['dcf']['value_per_share']:.2f}")
    if valuation.get("ddm"):
        print(f"DDM fair value:       ${valuation['ddm']['value_per_share']:.2f}")
    else:
        print(f"DDM:                  not applicable ({valuation.get('ddm_skipped_reason')})")
    print(f"WACC used:            {valuation['wacc']['wacc']:.2%}")

    flags = state.get("critic_flags", [])
    if flags:
        print(f"\nCritic flags ({len(flags)}):")
        for f in flags:
            print(f"  [{f['severity'].upper()}] {f['message']}")

    memo = state.get("memo_text")
    if memo:
        print("\n" + "=" * 60)
        print("INVESTMENT MEMO")
        print("=" * 60)
        print(memo)

        # Write memo to a file
        filename = f"{ticker}_valuation_memo.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(memo)
            print(f"\n[Info] Memo saved to file: {filename}")
        except Exception as e:
            print(f"\n[Warning] Failed to save memo to file: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python3 run_valuagent.py TICKER   - Run CLI valuation for a ticker")
        print("  python3 run_valuagent.py --web    - Start the web dashboard server")
        sys.exit(1)

    arg = sys.argv[1]
    if arg.lower() == "--web":
        import uvicorn
        port = int(os.environ.get("PORT", 8080))
        print(f"Starting web dashboard on http://127.0.0.1:{port}...")
        uvicorn.run("web.web_app:app", host="127.0.0.1", port=port, reload=True)
    else:
        ticker_arg = arg.upper()
        asyncio.run(run(ticker_arg))
