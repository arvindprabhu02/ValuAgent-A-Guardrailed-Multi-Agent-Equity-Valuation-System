"""
ValuAgent MCP Server

Exposes financial data retrieval as MCP tools so any MCP-compatible agent
(the ADK Data Retrieval Agent, Antigravity's orchestrator via
register_skill, or any other MCP client) can call them without needing
to know anything about yfinance directly.

Run standalone for local testing:
    python3 -m mcp_server.server

Run as an MCP server for a client to connect to via stdio:
    python3 mcp_server/server.py
"""

from mcp.server.fastmcp import FastMCP

# Support being launched two different ways:
#   1. As a package module: `python -m mcp_server.server` (relative import works)
#   2. As a standalone script by a subprocess launcher that only knows the
#      file path, e.g. ADK's StdioConnectionParams (relative import fails
#      because there's no parent package in that execution context)
# The try/except below makes this file work either way without the caller
# needing to know which mode it's in.
try:
    from . import data_fetch
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from mcp_server import data_fetch

mcp = FastMCP("valuagent-financial-data")


@mcp.tool()
def get_company_profile(ticker: str) -> dict:
    """
    Fetch company-level fundamentals needed for valuation: market cap,
    beta, total debt, cash, shares outstanding, current price, and
    sector/industry classification.

    Args:
        ticker: Stock ticker symbol, e.g. "AAPL", "MSFT", "INFY.NS"
    """
    return data_fetch.get_company_profile(ticker)


@mcp.tool()
def get_cash_flow_statement(ticker: str, years: int = 4) -> dict:
    """
    Fetch historical operating cash flow and capital expenditure for the
    trailing N fiscal years, used to derive historical FCFF trend for
    DCF projection.

    Args:
        ticker: Stock ticker symbol
        years: Number of most recent fiscal years to return (default 4)
    """
    return data_fetch.get_cash_flow_statement(ticker, years)


@mcp.tool()
def get_dividend_history(ticker: str, years: int = 5) -> dict:
    """
    Fetch annual dividend-per-share totals for the trailing N years, used
    as the historical base for DDM growth-rate estimation. Raises a clear
    error for non-dividend-paying stocks rather than returning empty data.

    Args:
        ticker: Stock ticker symbol
        years: Number of most recent years to return (default 5)
    """
    return data_fetch.get_dividend_history(ticker, years)


@mcp.tool()
def get_price_history(ticker: str, period: str = "1y") -> dict:
    """
    Fetch historical closing prices, used by the Critic/Guardrail agent to
    compare model output (DCF/DDM value per share) against actual market price.

    Args:
        ticker: Stock ticker symbol
        period: yfinance period string, e.g. "1mo", "6mo", "1y", "5y"
    """
    return data_fetch.get_price_history(ticker, period)


if __name__ == "__main__":
    mcp.run(transport="stdio")
