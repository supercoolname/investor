"""
Fetches financial data from Yahoo Finance via yfinance.

Key Inputs Needed for DCF Model:
+---------------------+-------------------------------------------------------+
| Input               | Description                                           |
+---------------------+-------------------------------------------------------+
| FCF                 | Free Cash Flow = Operating Cash Flow - CapEx          |
| Growth rate (near)  | e.g. 10-20% for growth stocks                         |
| Growth rate (term.) | e.g. 2-3% perpetual / terminal growth                 |
| WACC / Discount     | Weighted Avg Cost of Capital, typically 8-12%         |
| Net Debt            | Total Debt - Cash & Equivalents                       |
| Shares Outstanding  | From balance sheet / info                             |
+---------------------+-------------------------------------------------------+
"""

import yfinance as yf


def fetch_stock_data(ticker: str) -> dict:
    """
    Pulls all inputs needed for DCF from Yahoo Finance.

    Returns a dict with:
        - fcf: most recent annual Free Cash Flow
        - net_debt: Total Debt - Cash
        - shares_outstanding: shares outstanding
        - current_price: latest market price
        - company_name: display name
    Raises ValueError if data is unavailable or insufficient.
    """
    stock = yf.Ticker(ticker)
    info = stock.info

    # Current price
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not current_price:
        raise ValueError(f"Could not fetch current price for '{ticker}'. Check the ticker symbol.")

    # Free Cash Flow from cash flow statement
    cf = stock.cashflow
    if cf is None or cf.empty:
        raise ValueError(f"No cash flow data available for '{ticker}'.")

    # yfinance rows: "Free Cash Flow" or derive from operating CF - capex
    if "Free Cash Flow" in cf.index:
        fcf_series = cf.loc["Free Cash Flow"].dropna()
    elif "Operating Cash Flow" in cf.index and "Capital Expenditure" in cf.index:
        fcf_series = (
            cf.loc["Operating Cash Flow"] + cf.loc["Capital Expenditure"]
        ).dropna()
    else:
        raise ValueError(f"Cannot compute Free Cash Flow for '{ticker}'.")

    if fcf_series.empty:
        raise ValueError(f"Free Cash Flow data is empty for '{ticker}'.")

    fcf = float(fcf_series.iloc[0])  # most recent year

    # Net Debt = Total Debt - Cash
    balance = stock.balance_sheet
    total_debt = 0.0
    cash = 0.0

    if balance is not None and not balance.empty:
        if "Total Debt" in balance.index:
            total_debt = float(balance.loc["Total Debt"].iloc[0] or 0)
        if "Cash And Cash Equivalents" in balance.index:
            cash = float(balance.loc["Cash And Cash Equivalents"].iloc[0] or 0)
        elif "Cash Cash Equivalents And Short Term Investments" in balance.index:
            cash = float(
                balance.loc["Cash Cash Equivalents And Short Term Investments"].iloc[0] or 0
            )

    net_debt = total_debt - cash

    # Shares outstanding
    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    if not shares:
        raise ValueError(f"No shares outstanding data for '{ticker}'.")

    company_name = info.get("shortName") or ticker.upper()

    # Additional raw fields for display
    market_cap = info.get("marketCap")
    operating_cash_flow = float(cf.loc["Operating Cash Flow"].iloc[0]) if "Operating Cash Flow" in cf.index else None
    capex = float(cf.loc["Capital Expenditure"].iloc[0]) if "Capital Expenditure" in cf.index else None
    revenue = info.get("totalRevenue")
    ebitda = info.get("ebitda")
    pe_ratio = info.get("trailingPE")
    sector = info.get("sector")
    industry = info.get("industry")

    return {
        "fcf": fcf,
        "net_debt": net_debt,
        "total_debt": total_debt,
        "cash": cash,
        "shares_outstanding": float(shares),
        "current_price": float(current_price),
        "company_name": company_name,
        "market_cap": market_cap,
        "operating_cash_flow": operating_cash_flow,
        "capex": capex,
        "revenue": revenue,
        "ebitda": ebitda,
        "pe_ratio": pe_ratio,
        "sector": sector,
        "industry": industry,
    }
