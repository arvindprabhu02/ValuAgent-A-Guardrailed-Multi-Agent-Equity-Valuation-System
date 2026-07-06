"""
LIVE test against real Yahoo Finance data. Requires actual internet access.

This will NOT work inside a network-restricted sandbox -- run it on your
own machine before trusting the MCP server against real tickers.

Run with: python3 test_data_fetch_live.py
"""

from mcp_server import data_fetch


def main():
    ticker = "AAPL"  # change to any real ticker to test

    print(f"--- Testing live data fetch for {ticker} ---\n")

    print("1) Company profile:")
    profile = data_fetch.get_company_profile(ticker)
    for k, v in profile.items():
        print(f"   {k}: {v}")

    print("\n2) Cash flow statement (last 4 years):")
    cf = data_fetch.get_cash_flow_statement(ticker, years=4)
    print("   Operating Cash Flow by year:", cf["operating_cash_flow_by_year"])
    print("   Capital Expenditure by year:", cf["capital_expenditure_by_year"])

    print("\n3) Dividend history (last 5 years):")
    try:
        div = data_fetch.get_dividend_history(ticker, years=5)
        print("   Annual dividends per share:", div["annual_dividends_per_share"])
    except data_fetch.DataFetchError as e:
        print(f"   (Expected for non-dividend stocks) {e}")

    print("\n4) Price history (last 1 month):")
    price = data_fetch.get_price_history(ticker, period="1mo")
    print(f"   Latest close: {price['latest_close']}")
    print(f"   Number of trading days returned: {len(price['close_by_date'])}")

    print("\n--- All live calls completed without error ---")
    print("If any section above looks wrong (missing fields, zero values,")
    print("unexpected structure), yfinance's response format may have")
    print("changed -- check data_fetch.py's field-name assumptions.")


if __name__ == "__main__":
    main()
