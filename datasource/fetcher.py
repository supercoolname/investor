"""
Fetches financial data from Yahoo Finance via yfinance.

Key Inputs Needed for DCF Model:
+---------------------+-------------------------------------------------------+
| Input               | Description                                           |
+---------------------+-------------------------------------------------------+
| FCF                 | Free Cash Flow = Operating Cash Flow - CapEx          |
| NOPAT               | EBIT × (1 − effective tax rate) — pre-interest        |
| Growth rate (near)  | e.g. 10-20% for growth stocks                         |
| Growth rate (term.) | e.g. 2-3% perpetual / terminal growth                 |
| WACC / Discount     | Weighted Avg Cost of Capital, typically 8-12%         |
| Net Debt            | Total Debt - Cash & Equivalents                       |
| Shares Outstanding  | From balance sheet / info                             |
+---------------------+-------------------------------------------------------+
"""

from dataclasses import dataclass

import yfinance as yf


@dataclass
class FinancialData:
    # Core valuation inputs
    fcf:                float
    net_debt:           float
    total_debt:         float
    cash:               float
    shares_outstanding: float
    current_price:      float
    company_name:       str

    # Income statement
    ebit:               float | None
    effective_tax_rate: float | None
    nopat:              float | None

    # Cash flow statement
    operating_cash_flow: float | None
    capex:               float | None
    sbc:                 float | None   # Stock-Based Compensation (non-cash, added back in Op CF)

    # Market / info
    market_cap: float | None
    revenue:    float | None
    ebitda:     float | None
    pe_ratio:   float | None
    sector:     str | None
    industry:   str | None


def fetch_stock_data(ticker: str) -> FinancialData:
    """
    Pulls all inputs needed for DCF from Yahoo Finance.

    Returns a FinancialData dataclass.
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

    fcf = float(fcf_series.iloc[0])

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

    # Cash flow statement fields
    operating_cash_flow = float(cf.loc["Operating Cash Flow"].iloc[0]) if "Operating Cash Flow" in cf.index else None
    capex = float(cf.loc["Capital Expenditure"].iloc[0]) if "Capital Expenditure" in cf.index else None
    sbc = float(cf.loc["Stock Based Compensation"].iloc[0]) if "Stock Based Compensation" in cf.index else None

    # Market / info fields
    market_cap = info.get("marketCap")
    revenue    = info.get("totalRevenue")
    ebitda     = info.get("ebitda")
    pe_ratio   = info.get("trailingPE")
    sector     = info.get("sector")
    industry   = info.get("industry")

    # NOPAT = EBIT × (1 − effective_tax_rate) for Three-Phase DCF
    ebit = None
    effective_tax_rate = None
    nopat = None
    income = stock.income_stmt
    if income is not None and not income.empty:
        if "EBIT" in income.index:
            ebit = float(income.loc["EBIT"].iloc[0])
        elif "Operating Income" in income.index:
            ebit = float(income.loc["Operating Income"].iloc[0])
        if ebit is not None:
            tax    = income.loc["Tax Provision"].iloc[0] if "Tax Provision" in income.index else None
            pretax = income.loc["Pretax Income"].iloc[0] if "Pretax Income" in income.index else None
            if tax is not None and pretax and float(pretax) > 0:
                effective_tax_rate = min(abs(float(tax)) / float(pretax), 1.0)
            nopat = ebit * (1 - (effective_tax_rate or 0.0))

    return FinancialData(
        fcf=fcf,
        net_debt=net_debt,
        total_debt=total_debt,
        cash=cash,
        shares_outstanding=float(shares),
        current_price=float(current_price),
        company_name=company_name,
        ebit=ebit,
        effective_tax_rate=effective_tax_rate,
        nopat=nopat,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        sbc=sbc,
        market_cap=market_cap,
        revenue=revenue,
        ebitda=ebitda,
        pe_ratio=pe_ratio,
        sector=sector,
        industry=industry,
    )
