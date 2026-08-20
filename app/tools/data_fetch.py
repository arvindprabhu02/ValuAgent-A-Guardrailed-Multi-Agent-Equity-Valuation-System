"""
Data fetching layer — wraps yfinance and normalizes its output into clean,
predictable dicts.

Design note: this module is the ONLY place in ValuAgent that talks to an
external data provider. Every other module (agents, MCP server) depends only
on the shapes defined here, never on yfinance's raw objects directly.
"""

import yfinance as yf
import pandas as pd


class DataFetchError(Exception):
    """Raised when required data cannot be retrieved or is structurally incomplete."""
    pass


def _require_ticker_exists(ticker_obj: "yf.Ticker", ticker_symbol: str) -> None:
    info = ticker_obj.info
    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
        raise DataFetchError(
            f"No usable market data found for ticker '{ticker_symbol}'. "
            f"It may be delisted, mistyped, or unsupported by the data provider."
        )


def get_company_profile(ticker_symbol: str) -> dict:
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
        "forward_pe": info.get("forwardPE"),
        "exchange": info.get("exchange"),
        "currency": info.get("financialCurrency"),
    }


def get_cash_flow_statement(ticker_symbol: str, years: int = 4) -> dict:
    t = yf.Ticker(ticker_symbol)
    cf = t.cashflow

    if cf is None or cf.empty:
        raise DataFetchError(f"No cash flow statement available for '{ticker_symbol}'.")

    def _row(possible_labels):
        for label in possible_labels:
            if label in cf.index:
                res = cf.loc[label].iloc[:years].to_dict()
                return {str(k.year if hasattr(k, "year") else k): float(v) for k, v in res.items() if pd.notna(v)}
        return {}

    ocf = _row(["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = _row(["Capital Expenditure", "Capital Expenditures"])
    dividends = _row(["Cash Dividends Paid"])
    buybacks = _row(["Repurchase Of Capital Stock"])
    sbc = _row(["Stock Based Compensation"])

    return {
        "ticker": ticker_symbol.upper(),
        "operating_cash_flow_by_year": ocf,
        "capital_expenditure_by_year": capex,
        "dividends_paid_by_year": dividends,
        "buybacks_by_year": buybacks,
        "stock_based_compensation_by_year": sbc,
    }


def get_dividend_history(ticker_symbol: str, years: int = 5) -> dict:
    t = yf.Ticker(ticker_symbol)
    dividends = t.dividends

    if dividends is None or dividends.empty:
        return {
            "ticker": ticker_symbol.upper(),
            "annual_dividends_per_share": {},
            "has_dividends": False,
        }

    annual = dividends.groupby(dividends.index.year).sum().tail(years)

    return {
        "ticker": ticker_symbol.upper(),
        "annual_dividends_per_share": {str(int(year)): float(v) for year, v in annual.items()},
        "has_dividends": True,
    }


def get_price_history(ticker_symbol: str, period: str = "1y") -> dict:
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


def get_balance_sheet(ticker_symbol: str, years: int = 4) -> dict:
    t = yf.Ticker(ticker_symbol)
    bs = t.balance_sheet

    if bs is None or bs.empty:
        return {"ticker": ticker_symbol.upper(), "data": {}}

    def _row(possible_labels):
        for label in possible_labels:
            if label in bs.index:
                res = bs.loc[label].iloc[:years].to_dict()
                return {str(k.year if hasattr(k, "year") else k): float(v) for k, v in res.items() if pd.notna(v)}
        return {}

    return {
        "ticker": ticker_symbol.upper(),
        "total_assets": _row(["Total Assets"]),
        "total_liabilities": _row(["Total Liabilities Net Minority Interest", "Total Liabilities"]),
        "stockholders_equity": _row(["Stockholders Equity", "Total Stockholder Equity"]),
        "current_assets": _row(["Current Assets"]),
        "current_liabilities": _row(["Current Liabilities"]),
        "cash_and_equivalents": _row(["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
        "receivables": _row(["Receivables", "Accounts Receivable"]),
        "total_debt": _row(["Total Debt"]),
        "current_debt": _row(["Current Debt And Capital Lease Obligation", "Current Debt"]),
        "long_term_debt": _row(["Long Term Debt And Capital Lease Obligation", "Long Term Debt"]),
    }


def get_income_statement(ticker_symbol: str, years: int = 4) -> dict:
    t = yf.Ticker(ticker_symbol)
    fin = t.financials

    if fin is None or fin.empty:
        return {"ticker": ticker_symbol.upper(), "data": {}}

    def _row(possible_labels):
        for label in possible_labels:
            if label in fin.index:
                res = fin.loc[label].iloc[:years].to_dict()
                return {str(k.year if hasattr(k, "year") else k): float(v) for k, v in res.items() if pd.notna(v)}
        return {}

    return {
        "ticker": ticker_symbol.upper(),
        "total_revenue": _row(["Total Revenue"]),
        "gross_profit": _row(["Gross Profit"]),
        "operating_income": _row(["Operating Income", "EBIT"]),
        "net_income": _row(["Net Income", "Net Income Common Stockholders"]),
        "diluted_eps": _row(["Diluted EPS"]),
        "diluted_shares": _row(["Diluted Average Shares"]),
        "research_development": _row(["Research And Development"]),
        "interest_expense": _row(["Interest Expense", "Interest Expense Non Operating"]),
        "ebitda": _row(["EBITDA", "Normalized EBITDA"]),
    }


def get_key_statistics(ticker_symbol: str) -> dict:
    t = yf.Ticker(ticker_symbol)
    info = t.info or {}

    res = {
        "ticker": ticker_symbol.upper(),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "price_to_book": info.get("priceToBook"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "peg_ratio": info.get("pegRatio"),
        "enterprise_value": info.get("enterpriseValue"),
        "market_cap": info.get("marketCap"),
        "held_percent_insiders": info.get("heldPercentInsiders"),
        "held_percent_institutions": info.get("heldPercentInstitutions"),
        "payout_ratio": info.get("payoutRatio"),
        "five_yr_avg_dividend_yield": info.get("fiveYearAvgDividendYield"),
        "dividend_yield": info.get("dividendYield"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "debt_to_equity": info.get("debtToEquity"),
        "revenue_growth": info.get("revenueGrowth"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "profit_margins": info.get("profitMargins"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_day_average": info.get("fiftyDayAverage"),
        "two_hundred_day_average": info.get("twoHundredDayAverage"),
        "return_on_assets": info.get("returnOnAssets"),
        "return_on_equity": info.get("returnOnEquity"),
    }
    
    try:
        bs = t.balance_sheet
        fin = t.financials
        if not bs.empty and not fin.empty:
            ebit = None
            if "EBIT" in fin.index: ebit = fin.loc["EBIT"].iloc[0]
            elif "Operating Income" in fin.index: ebit = fin.loc["Operating Income"].iloc[0]
            
            if "Total Assets" in bs.index and "Current Liabilities" in bs.index:
                total_assets = bs.loc["Total Assets"].iloc[0]
                current_liab = bs.loc["Current Liabilities"].iloc[0]
                if total_assets and current_liab:
                    capital_employed = total_assets - current_liab
                    if capital_employed and ebit:
                        res["roce"] = float(ebit / capital_employed)
            
            invested_capital = bs.loc["Invested Capital"].iloc[0] if "Invested Capital" in bs.index else None
            pretax = fin.loc["Pretax Income"].iloc[0] if "Pretax Income" in fin.index else None
            tax = fin.loc["Tax Provision"].iloc[0] if "Tax Provision" in fin.index else None
            if invested_capital and pretax and tax and pretax > 0 and ebit:
                tax_rate = tax / pretax
                nopat = ebit * (1 - tax_rate)
                res["roic"] = float(nopat / invested_capital)
    except Exception:
        pass

    return res


def get_insider_transactions(ticker_symbol: str) -> dict:
    t = yf.Ticker(ticker_symbol)
    try:
        df = t.insider_transactions
        if df is not None and not df.empty:
            records = df.head(10).to_dict(orient="records")
            clean_records = []
            for r in records:
                clean_r = {str(k): (str(v) if pd.notna(v) else None) for k, v in r.items()}
                clean_records.append(clean_r)
            return {"ticker": ticker_symbol.upper(), "transactions": clean_records}
    except Exception:
        pass
    return {"ticker": ticker_symbol.upper(), "transactions": []}


def get_multi_period_price_history(ticker_symbol: str) -> dict:
    t = yf.Ticker(ticker_symbol)
    hist = t.history(period="5y")

    if hist is None or hist.empty:
        return {"ticker": ticker_symbol.upper(), "history": {}}

    closes = hist["Close"]
    latest = float(closes.iloc[-1])

    def _get_historical(days):
        if len(closes) > days:
            return float(closes.iloc[-(days+1)])
        return float(closes.iloc[0])

    p_3m = _get_historical(63)
    p_1y = _get_historical(252)
    p_5y = float(closes.iloc[0])

    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_14 = float((100 - (100 / (1 + rs))).iloc[-1]) if len(closes) >= 14 else 50.0

    # Calculate average monthly returns
    monthly_closes = closes.resample('ME').last() if hasattr(closes, 'resample') else closes
    monthly_returns = monthly_closes.pct_change()
    
    # Last 12 months
    monthly_returns_1y = monthly_returns.tail(12)
    avg_monthly_return_1y = float(monthly_returns_1y.mean() * 100) if not monthly_returns_1y.empty else 0.0
    
    # Last 5 years (60 months)
    monthly_returns_5y = monthly_returns.tail(60)
    avg_monthly_return_5y = float(monthly_returns_5y.mean() * 100) if not monthly_returns_5y.empty else 0.0

    return {
        "ticker": ticker_symbol.upper(),
        "latest_price": latest,
        "price_3m_ago": p_3m,
        "price_1y_ago": p_1y,
        "price_5y_ago": p_5y,
        "return_3m_pct": ((latest - p_3m) / p_3m) * 100 if p_3m else 0.0,
        "return_1y_pct": ((latest - p_1y) / p_1y) * 100 if p_1y else 0.0,
        "return_5y_pct": ((latest - p_5y) / p_5y) * 100 if p_5y else 0.0,
        "avg_monthly_return_1y_pct": avg_monthly_return_1y,
        "avg_monthly_return_5y_pct": avg_monthly_return_5y,
        "rsi_14": rsi_14,
    }
def get_ohlc_data(ticker_symbol: str, period: str = '5y') -> dict:
    t = yf.Ticker(ticker_symbol)
    hist = t.history(period=period)
    if hist is None or hist.empty:
        return {}
    return {
        'dates': [str(d.date()) for d in hist.index],
        'opens': hist['Open'].tolist(),
        'highs': hist['High'].tolist(),
        'lows': hist['Low'].tolist(),
        'closes': hist['Close'].tolist(),
        'volumes': hist['Volume'].tolist()
    }
