"""
FastMCP Server exposing financial data retrieval tools to the ADK pipeline.
"""

import json
from mcp.server.fastmcp import FastMCP
from app.tools.data_fetch import (
    get_company_profile,
    get_cash_flow_statement,
    get_dividend_history,
    get_price_history,
    get_balance_sheet,
    get_income_statement,
    get_key_statistics,
    get_insider_transactions,
    get_multi_period_price_history,
    DataFetchError,
)

mcp = FastMCP("valuagent-financial-data")


@mcp.tool()
def fetch_company_profile(ticker: str) -> str:
    """Retrieves high-level company profile data (sector, price, market cap, debt, cash, shares)."""
    try:
        data = get_company_profile(ticker)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_cash_flow_statement(ticker: str, years: int = 4) -> str:
    """Retrieves historical operating cash flow, CapEx, buybacks, and SBC."""
    try:
        data = get_cash_flow_statement(ticker, years=years)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_dividend_history(ticker: str, years: int = 5) -> str:
    """Retrieves annual dividend per share history."""
    try:
        data = get_dividend_history(ticker, years=years)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_price_history(ticker: str, period: str = "1y") -> str:
    """Retrieves daily price history."""
    try:
        data = get_price_history(ticker, period=period)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_balance_sheet(ticker: str, years: int = 4) -> str:
    """Retrieves balance sheet line items (Assets, Debt, Cash, Equity, Current Assets/Liabilities)."""
    try:
        data = get_balance_sheet(ticker, years=years)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_income_statement(ticker: str, years: int = 4) -> str:
    """Retrieves income statement line items (Revenue, Margins, EPS, EBITDA, R&D)."""
    try:
        data = get_income_statement(ticker, years=years)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_key_statistics(ticker: str) -> str:
    """Retrieves valuation multiples (P/E, P/S, P/B, EV/EBITDA, PEG) and ownership statistics."""
    try:
        data = get_key_statistics(ticker)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_insider_transactions(ticker: str) -> str:
    """Retrieves recent insider buy and sell activity."""
    try:
        data = get_insider_transactions(ticker)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def fetch_multi_period_price_history(ticker: str) -> str:
    """Retrieves multi-horizon returns (3M, 1Y, 5Y), RSI(14), and trend indicators."""
    try:
        data = get_multi_period_price_history(ticker)
        return json.dumps(data)
    except DataFetchError as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
