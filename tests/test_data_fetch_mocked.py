"""
Tests for the data_fetch parsing/normalization logic, using mocked
yfinance responses.

Why mocked and not live: this sandbox's network is restricted and cannot
reach Yahoo Finance's endpoints. These tests validate that OUR parsing
code correctly handles yfinance's data shapes -- they do NOT validate
that yfinance itself is currently returning correct data. Before trusting
this in production, run test_data_fetch_live.py (network required) against
a real ticker.

Run with: python3 test_data_fetch_mocked.py
"""

from unittest.mock import patch, MagicMock
import pandas as pd
from mcp_server import data_fetch


def test_get_company_profile():
    fake_info = {
        "longName": "Example Corp",
        "sector": "Technology",
        "industry": "Software",
        "currentPrice": 150.0,
        "marketCap": 2_500_000_000,
        "beta": 1.15,
        "sharesOutstanding": 16_000_000,
        "totalDebt": 100_000_000,
        "totalCash": 50_000_000,
        "trailingPE": 28.5,
        "forwardPE": 25.0,
    }

    with patch("mcp_server.data_fetch.yf.Ticker") as MockTicker:
        instance = MockTicker.return_value
        instance.info = fake_info

        result = data_fetch.get_company_profile("EXMPL")

    assert result["ticker"] == "EXMPL"
    assert result["current_price"] == 150.0
    assert result["market_cap"] == 2_500_000_000
    assert result["beta"] == 1.15
    print("test_get_company_profile PASSED:", result)


def test_get_company_profile_invalid_ticker_raises():
    with patch("mcp_server.data_fetch.yf.Ticker") as MockTicker:
        instance = MockTicker.return_value
        instance.info = {}  # yfinance returns empty dict for bad tickers

        try:
            data_fetch.get_company_profile("NOTREAL")
            assert False, "Expected DataFetchError"
        except data_fetch.DataFetchError:
            print("test_get_company_profile_invalid_ticker_raises PASSED")


def test_get_cash_flow_statement():
    fake_cashflow = pd.DataFrame(
        {
            pd.Timestamp("2025-12-31"): {"Operating Cash Flow": 500.0, "Capital Expenditure": -80.0},
            pd.Timestamp("2024-12-31"): {"Operating Cash Flow": 450.0, "Capital Expenditure": -70.0},
        }
    )

    with patch("mcp_server.data_fetch.yf.Ticker") as MockTicker:
        instance = MockTicker.return_value
        instance.cashflow = fake_cashflow

        result = data_fetch.get_cash_flow_statement("EXMPL", years=2)

    assert result["ticker"] == "EXMPL"
    assert len(result["operating_cash_flow_by_year"]) == 2
    assert len(result["capital_expenditure_by_year"]) == 2
    print("test_get_cash_flow_statement PASSED:", result)


def test_get_cash_flow_statement_missing_line_items_raises():
    fake_cashflow = pd.DataFrame({pd.Timestamp("2025-12-31"): {"Some Other Line": 10.0}})

    with patch("mcp_server.data_fetch.yf.Ticker") as MockTicker:
        instance = MockTicker.return_value
        instance.cashflow = fake_cashflow

        try:
            data_fetch.get_cash_flow_statement("EXMPL")
            assert False, "Expected DataFetchError for missing line items"
        except data_fetch.DataFetchError:
            print("test_get_cash_flow_statement_missing_line_items_raises PASSED")


def test_get_dividend_history():
    dates = pd.to_datetime(["2023-03-01", "2023-09-01", "2024-03-01", "2024-09-01"])
    fake_dividends = pd.Series([0.5, 0.5, 0.55, 0.55], index=dates)

    with patch("mcp_server.data_fetch.yf.Ticker") as MockTicker:
        instance = MockTicker.return_value
        instance.dividends = fake_dividends

        result = data_fetch.get_dividend_history("EXMPL", years=5)

    assert result["ticker"] == "EXMPL"
    assert result["annual_dividends_per_share"]["2023"] == 1.0
    assert result["annual_dividends_per_share"]["2024"] == 1.10
    print("test_get_dividend_history PASSED:", result)


def test_get_dividend_history_no_dividends_raises():
    with patch("mcp_server.data_fetch.yf.Ticker") as MockTicker:
        instance = MockTicker.return_value
        instance.dividends = pd.Series([], dtype=float)

        try:
            data_fetch.get_dividend_history("NODIV")
            assert False, "Expected DataFetchError for non-dividend-paying stock"
        except data_fetch.DataFetchError:
            print("test_get_dividend_history_no_dividends_raises PASSED")


def test_get_price_history():
    dates = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"])
    fake_hist = pd.DataFrame({"Close": [100.0, 102.0, 101.5]}, index=dates)

    with patch("mcp_server.data_fetch.yf.Ticker") as MockTicker:
        instance = MockTicker.return_value
        instance.history.return_value = fake_hist

        result = data_fetch.get_price_history("EXMPL", period="1mo")

    assert result["ticker"] == "EXMPL"
    assert result["latest_close"] == 101.5
    assert len(result["close_by_date"]) == 3
    print("test_get_price_history PASSED:", result)


if __name__ == "__main__":
    test_get_company_profile()
    test_get_company_profile_invalid_ticker_raises()
    test_get_cash_flow_statement()
    test_get_cash_flow_statement_missing_line_items_raises()
    test_get_dividend_history()
    test_get_dividend_history_no_dividends_raises()
    test_get_price_history()
    print("\nAll mocked data_fetch tests passed.")
