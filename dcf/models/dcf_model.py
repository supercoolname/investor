"""
Core DCF growth engine.

Growth rate declines linearly from g_start (year 1) to g_terminal (year n),
then continues at g_terminal in perpetuity (Gordon Growth terminal value).
"""


def _dcf_linear_growth(
    fcf: float,
    g_start: float,
    g_terminal: float,
    wacc: float,
    net_debt: float,
    shares_outstanding: float,
    years: int,
) -> dict:
    """
    DCF where near-term growth declines linearly from g_start (year 1) to
    g_terminal (year `years`), then continues at g_terminal in perpetuity.

    Args:
        fcf: Base Free Cash Flow (most recent annual, in dollars)
        g_start: Near-term growth rate at year 1 (e.g. 0.10)
        g_terminal: Perpetual terminal growth rate (e.g. 0.025)
        wacc: Weighted Average Cost of Capital. Discount rate / WACC (e.g. 0.10) 
        net_debt: Total Debt - Cash (in dollars)
        shares_outstanding: Number of shares
        years: Forecast horizon

    Returns:
        dict with keys:
            intrinsic_price, enterprise_value, equity_value,
            pv_fcfs, pv_terminal, rows (year-by-year breakdown)
    """
    if wacc <= g_terminal:
        raise ValueError("WACC must be greater than terminal growth rate.")

    rows = []
    pv_fcfs = 0.0
    current_fcf = fcf

    for t in range(1, years + 1):
        # Linear interpolation: year 1 → g_start, year N → g_terminal
        alpha = (t - 1) / (years - 1) if years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha
        # assmues FCF growths for free. Non additional reinvestment required. Not true for capex heavy businesses.
        current_fcf *= (1 + g_t)
        discount_factor = (1 + wacc) ** t
        pv = current_fcf / discount_factor
        pv_fcfs += pv
        rows.append({
            "Year": t,
            "Growth Rate": f"{g_t * 100:.1f}%",
            "Projected FCF ($B)": current_fcf / 1e9,
            "Discount Factor": discount_factor,
            "PV of FCF ($B)": pv / 1e9,
        })

    terminal_value = current_fcf * (1 + g_terminal) / (wacc - g_terminal)
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
