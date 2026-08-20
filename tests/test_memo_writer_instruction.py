"""
Tests for memo writer instruction prompt formatting under facts-only architecture.
"""

from app.agents.memo_prompt import build_memo_prompt


def test_build_memo_prompt():
    state = {
        "ticker": "AAPL",
        "fundamental_analysis": {
            "balance_sheet": {
                "current_ratio": 1.07,
                "debt_to_equity": 1.87,
                "net_debt": 49200000000.0,
                "interest_coverage": 29.1,
                "net_debt_to_ebitda": 0.8,
            },
            "profitability": {
                "revenue_growth_yoy": 2.1,
                "gross_margin": 46.2,
                "operating_margin": 30.7,
                "net_margin": 23.1,
                "rd_intensity": 7.8,
            },
            "cash_flow": {
                "free_cash_flow": 110500000000.0,
                "fcf_yield": 3.6,
                "fcf_conversion": 1.05,
            },
            "per_share": {
                "diluted_eps": 6.42,
                "eps_growth_yoy": 9.2,
                "fcf_per_share": 6.85,
            },
            "price_trend": {
                "current_price": 198.50,
                "return_1y_pct": 24.5,
                "sma_signal": "BULLISH",
            },
            "valuation_multiples": {
                "trailing_pe": 30.9,
                "forward_pe": 28.1,
            },
        },
        "industry_comparison": {
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "sector_etf_ticker": "XLK",
            "company_1y_return_pct": 24.5,
            "sector_etf_1y_return_pct": 18.2,
            "outperformance_pct": 6.3,
        },
        "critic_flags": [],
    }

    prompt = build_memo_prompt(state)
    assert "AAPL" in prompt
    assert "Technology" in prompt
    assert "198.5" in prompt
    assert "30.9x" in prompt
    assert "+24.5%" in prompt
