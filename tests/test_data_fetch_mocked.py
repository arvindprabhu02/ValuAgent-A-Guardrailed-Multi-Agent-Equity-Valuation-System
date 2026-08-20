"""
Mocked unit tests for data_fetch module.
"""

from unittest.mock import MagicMock, patch
import pytest
from app.tools.data_fetch import (
    get_cash_flow_statement,
    get_dividend_history,
    DataFetchError,
)


def test_get_cash_flow_statement_missing_line_items_raises():
    mock_ticker = MagicMock()
    mock_ticker.cashflow = None

    with patch("yfinance.Ticker", return_value=mock_ticker):
        with pytest.raises(DataFetchError):
            get_cash_flow_statement("BADCO")


def test_get_dividend_history_no_dividends_returns_empty():
    mock_ticker = MagicMock()
    mock_ticker.dividends = None

    with patch("yfinance.Ticker", return_value=mock_ticker):
        res = get_dividend_history("NODIVCO")
        assert res["has_dividends"] is False
        assert res["annual_dividends_per_share"] == {}
