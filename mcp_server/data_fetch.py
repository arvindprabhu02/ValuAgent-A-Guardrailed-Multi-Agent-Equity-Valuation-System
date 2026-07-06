"""
Data fetching layer — wraps yfinance and normalizes its output into clean,
predictable dicts.

Design note: this module is the ONLY place in ValuAgent that talks to an
external data provider. Every other module (valuation/*, the MCP server,
the ADK agents) depends only on the shapes defined here, never on
yfinance's raw objects directly. That means if you swap providers later
(e.g. add Alpha Vantage as a fallback), only this file changes.

IMPORTANT — network requirement: this module requires outbound internet
access to Yahoo Finance's endpoints. It will raise a clear error if that
access is unavailable rather than failing silently or returning partial
data, since silently-wrong financial inputs are worse than a loud failure.
"""

import yfinance as yf


class DataFetchError(Exception):
    """Raised when required data cannot be retrieved or is structurally incomplete."""
    pass


def _require_ticker_exists(ticker_obj: "yf.Ticker", ticker_symbol: str) -> None:
    """
    yfinance does not always raise cleanly for an invalid ticker — it can
    return empty DataFrames instead. This checks for that case explicitly
    so callers get a clear error rather than a confusing downstream failure.
    """
    info = ticker_obj.info
    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        raise DataFetchError(
            f"No usable market data found for ticker '{ticker_symbol}'. "
            f"It may be delisted, mistyped, or unsupported by the data provider."
        )


def get_company_profile(ticker_symbol: str) -> dict:
    """
    Returns the key company-level figures needed as inputs to WACC/DCF/DDM:
    market cap, beta, total debt, cash, shares outstanding, current price,
    sector (for the Critic Agent's sector P/E sanity check).
    """
    t = yf.Ticker(ticker_symbol)
    _require_ticker_exists(t, ticker_symbol)
    info = t.info

    return {
        "ticker": ticker_symbol.upper(),
        "long_name": info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "beta": info.get("beta"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "trailing_pe": info.get("trailingPE"),
        "sector_pe_proxy": info.get("forwardPE"),  # yfinance has no direct sector PE; see README caveat
        "exchange": info.get("exchange"),
        "currency": info.get("financialCurrency"),
    }


def get_cash_flow_statement(ticker_symbol: str, years: int = 4) -> dict:
    """
    Returns historical operating cash flow and capital expenditure, the two
    inputs needed to derive historical FCFF (FCFF = OCF - CapEx, simplified
    form ignoring interest tax shield adjustments — see README for the
    assumption this simplification makes).
    """
    t = yf.Ticker(ticker_symbol)
    cf = t.cashflow  # DataFrame: rows = line items, columns = fiscal years

    if cf is None or cf.empty:
        raise DataFetchError(f"No cash flow statement available for '{ticker_symbol}'.")

    def _row(possible_labels):
        for label in possible_labels:
            if label in cf.index:
                return cf.loc[label].iloc[:years].to_dict()
        return {}

    operating_cash_flow = _row(["Operating Cash Flow", "Total Cash From Operating Activities"])
    capital_expenditure = _row(["Capital Expenditure", "Capital Expenditures"])

    if not operating_cash_flow or not capital_expenditure:
        raise DataFetchError(
            f"Cash flow statement for '{ticker_symbol}' is missing required line items "
            f"(Operating Cash Flow / Capital Expenditure). Provider data may have changed format."
        )

    return {
        "ticker": ticker_symbol.upper(),
        "operating_cash_flow_by_year": {str(k): v for k, v in operating_cash_flow.items()},
        "capital_expenditure_by_year": {str(k): v for k, v in capital_expenditure.items()},
    }


def get_dividend_history(ticker_symbol: str, years: int = 5) -> dict:
    """
    Returns annual dividend-per-share totals for the trailing N years, for
    use as the historical base in DDM growth-rate estimation.
    """
    t = yf.Ticker(ticker_symbol)
    dividends = t.dividends  # pandas Series, indexed by ex-dividend date

    if dividends is None or dividends.empty:
        raise DataFetchError(
            f"No dividend history found for '{ticker_symbol}'. "
            f"This is expected for non-dividend-paying stocks — DDM is not "
            f"applicable to such companies; use DCF only."
        )

    annual = dividends.groupby(dividends.index.year).sum()
    annual = annual.tail(years)

    return {
        "ticker": ticker_symbol.upper(),
        "annual_dividends_per_share": {str(int(year)): float(v) for year, v in annual.items()},
    }


def get_price_history(ticker_symbol: str, period: str = "1y") -> dict:
    """
    Returns closing price history, used for the Critic Agent's
    market-price-vs-model-output sanity check.
    """
    t = yf.Ticker(ticker_symbol)
    hist = t.history(period=period)

    if hist is None or hist.empty:
        raise DataFetchError(f"No price history available for '{ticker_symbol}'.")

    closes = hist["Close"]
    return {
        "ticker": ticker_symbol.upper(),
        "period": period,
        "latest_close": float(closes.iloc[-1]),
        "close_by_date": {str(idx.date()): float(v) for idx, v in closes.items()},
    }
