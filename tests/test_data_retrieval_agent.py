"""
Test harness for DataRetrievalAgent, using the REAL google-adk Runner and
the REAL MCP server (which in turn calls REAL yfinance).

This is deliberately an integration test, not a unit test with mocks --
the whole point of this step is to confirm the ADK <-> MCP <-> yfinance
chain actually works end-to-end, since each of those three layers has
already been unit-tested / mocked separately.

Requires internet access (same requirement as test_data_fetch_live.py).

Run with: python3 test_data_retrieval_agent.py
"""

import asyncio

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.data_retrieval_agent import DataRetrievalAgent


async def main():
    ticker = "MSFT"  # change to test other tickers

    agent = DataRetrievalAgent()
    session_service = InMemorySessionService()

    app_name = "valuagent_test"
    user_id = "test_user"

    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        state={"ticker": ticker},
    )

    runner = Runner(
        agent=agent,
        app_name=app_name,
        session_service=session_service,
    )

    print(f"--- Running DataRetrievalAgent for {ticker} ---\n")

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=f"Fetch financial data for {ticker}")],
        ),
    ):
        author = event.author
        text = None
        if event.content and event.content.parts:
            text = event.content.parts[0].text
        print(f"[event from {author}] {text}")

    # Read back the final session state to confirm data landed correctly
    final_session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session.id
    )

    print("\n--- Final session state ---")
    error = final_session.state.get("financial_data_error")
    if error:
        print(f"ERROR: {error}")
        return

    data = final_session.state.get("financial_data")
    if not data:
        print("No financial_data found in session state -- something went wrong silently.")
        return

    print(f"Ticker: {data['ticker']}")
    print(f"Company: {data['company_profile'].get('long_name')}")
    print(f"Current price: {data['company_profile'].get('current_price')}")
    print(f"Beta: {data['company_profile'].get('beta')}")
    print(f"Cash flow years returned: {len(data['cash_flow']['operating_cash_flow_by_year'])}")
    if data.get("dividend_history"):
        print(f"Dividend years returned: {len(data['dividend_history']['annual_dividends_per_share'])}")
    else:
        print(f"No dividend history: {data.get('dividend_history_error')}")
    print(f"Price history trading days: {len(data['price_history']['close_by_date'])}")

    print("\n--- Test completed successfully ---")


if __name__ == "__main__":
    asyncio.run(main())
