"""
DCF (Discounted Cash Flow) valuation model.

Formula:
    Intrinsic Value = Σ [FCF_t / (1 + r)^t]  +  TV / (1 + r)^n  -  Net Debt
                                                                    ──────────────────
                                                                    Shares Outstanding

Where:
    FCF_t  = FCF_0 * (1 + near_growth)^t          projected free cash flow in year t
    r      = WACC (discount rate)
    TV     = FCF_n * (1 + g) / (r - g)             terminal value (Gordon Growth)
    g      = terminal growth rate
    n      = forecast years

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


def run_dcf(
    fcf: float,
    near_growth: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    years: int = 5,
) -> dict:
    """
    Runs the DCF model and returns a breakdown of results.

    Args:
        fcf: Base Free Cash Flow (most recent annual, in dollars)
        near_growth: Near-term annual FCF growth rate (e.g. 0.10 for 10%)
        wacc: Discount rate / WACC (e.g. 0.10 for 10%)
        terminal_growth: Perpetual growth rate beyond forecast (e.g. 0.025)
        net_debt: Total Debt - Cash (in dollars)
        shares_outstanding: Number of shares
        years: Forecast horizon (default 5)

    Returns:
        dict with keys:
            intrinsic_price, enterprise_value, equity_value,
            pv_fcfs, pv_terminal, rows (year-by-year breakdown)
    """
    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth rate.")

    rows = []
    pv_fcfs = 0.0

    for t in range(1, years + 1):
        projected_fcf = fcf * (1 + near_growth) ** t
        discount_factor = (1 + wacc) ** t
        pv = projected_fcf / discount_factor
        pv_fcfs += pv
        rows.append({
            "Year": t,
            "Projected FCF ($B)": projected_fcf / 1e9,
            "Discount Factor": discount_factor,
            "PV of FCF ($B)": pv / 1e9,
        })

    # Terminal Value
    fcf_final = fcf * (1 + near_growth) ** years
    terminal_value = fcf_final * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** years

    enterprise_value = pv_fcfs + pv_terminal
    equity_value = enterprise_value - net_debt
    intrinsic_price = equity_value / shares_outstanding

    return {
        "intrinsic_price": intrinsic_price,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "pv_fcfs": pv_fcfs,
        "pv_terminal": pv_terminal,
        "rows": rows,
    }
