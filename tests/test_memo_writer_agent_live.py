"""
LIVE test for the Memo Writer Agent -- requires a real Gemini API key and
internet access to Google's API. This was NOT run during the build
(no API key or network access available in the build sandbox).

Setup:
    1. Get an API key from https://aistudio.google.com/apikey
    2. Set it as an environment variable:
         Windows (PowerShell): $env:GOOGLE_API_KEY="your-key-here"
         Mac/Linux:             export GOOGLE_API_KEY="your-key-here"
    3. Run: python3 test_memo_writer_agent_live.py

If you get a "model not found" error, the MODEL_NAME default in
memo_writer_agent.py may be outdated -- check https://ai.google.dev for
current model names and either edit that file or set:
    export VALUAGENT_MEMO_MODEL="whatever-model-name-is-current"
"""

import asyncio
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.memo_writer_agent import memo_writer_agent


FAKE_VALUATION_RESULT = {
    "ticker": "TESTCO",
    "dcf": {
        "value_per_share": 67.15,
        "enterprise_value": 990_000_000_000,
        "equity_value": 973_000_000_000,
    },
    "ddm": {
        "value_per_share": 14.31,
        "next_year_dividend": 1.06,
    },
    "wacc": {"wacc": 0.099, "cost_of_equity": 0.11},
    "current_market_price": 300.0,
    "assumptions_used": {"terminal_growth_rate": 0.025},
}

FAKE_CRITIC_FLAGS = [
    {"severity": "warning", "check": "dcf_market_divergence",
     "message": "DCF fair value ($67.15) is 78% below the current market price ($300.00)."},
    {"severity": "warning", "check": "ddm_low_payout_ratio",
     "message": "TESTCO's implied dividend yield is only 0.35%. DDM will systematically understate fair value."},
]

FAKE_SENSITIVITY_RESULT = {
    "wacc_values": [0.079, 0.089, 0.099, 0.109, 0.119],
    "growth_values": [0.015, 0.025, 0.035],
    "grid": [[100.5, 110.2, 125.8], [90.1, 99.0, 110.3], [80.2, 87.3, 95.1], [72.4, 78.6, 85.2], [65.1, 70.3, 76.8]],
}


async def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: No GROQ_API_KEY found in environment.")
        return

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="memo_test",
        user_id="u",
        state={
            "valuation_result": FAKE_VALUATION_RESULT,
            "critic_flags": FAKE_CRITIC_FLAGS,
            "sensitivity_result": FAKE_SENSITIVITY_RESULT,
        },
    )
    runner = Runner(agent=memo_writer_agent, app_name="memo_test", session_service=session_service)

    print("--- Calling the real LLM to generate a memo (this costs a small amount) ---\n")

    async for event in runner.run_async(
        user_id="u",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text="Write the memo.")]),
    ):
        if event.content and event.content.parts:
            text = event.content.parts[0].text
            if text:
                print(text)

    final_session = await session_service.get_session(app_name="memo_test", user_id="u", session_id=session.id)
    memo = final_session.state.get("memo_text")

    print("\n--- Sanity checks on the generated memo ---")
    if memo is None:
        print("FAIL: no memo_text found in session state.")
        return

    # Basic hallucination guard: check that numbers stated in the memo
    # actually appear in the source data, not just that SOME numbers appear.
    expected_figures = ["67.15", "14.31", "300", "9.9", "99", "9.90"]
    found = [f for f in expected_figures if f in memo]
    print(f"Expected source figures found in memo: {found}")
    if len(found) < 3:
        print("WARNING: fewer expected figures found than anticipated -- "
              "manually review the memo below for any invented numbers.")

    print("\n--- Full memo text ---")
    print(memo)


if __name__ == "__main__":
    asyncio.run(main())
