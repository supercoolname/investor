"""
Damodaran ROIC-based DCF model.

Growth requires reinvestment. Each year:
    reinvestment_rate = g_t / roic
    FCF_t             = NOPAT_t × (1 − reinvestment_rate)

When roic → ∞: degenerates to simple FCF growth (no reinvestment needed).
When roic = wacc: growth adds zero excess value (competitive equilibrium).
When roic < wacc: growth destroys value.

Terminal value uses roic_terminal (defaults to wacc per Damodaran — no excess
returns in perpetuity under competition).
"""


def _damodaran_dcf(
    nopat: float,
    roic: float,
    g_start: float,
    g_terminal: float,
    wacc: float,
    net_debt: float,
    shares_outstanding: float,
    years: int,
    roic_terminal: float | None = None,
) -> dict:
    """
    DCF where growth is funded by reinvestment scaled by ROIC.

    Args:
        nopat: Base-year Net Operating Profit After Tax ($)
        roic: Near-term Return on Invested Capital (e.g. 0.20 for 20%)
        g_start: Near-term growth rate at year 1 (e.g. 0.15)
        g_terminal: Perpetual terminal growth rate (e.g. 0.025)
        wacc: Discount rate / WACC (e.g. 0.10)
        net_debt: Total Debt - Cash ($)
        shares_outstanding: Number of shares
        years: Forecast horizon
        roic_terminal: ROIC in terminal period. Defaults to wacc (zero excess
            returns in perpetuity — Damodaran's recommended default).

    Returns:
        dict with keys:
            intrinsic_price, enterprise_value, equity_value,
            pv_fcfs, pv_terminal, terminal_reinvestment_rate, terminal_fcf,
            rows (year-by-year breakdown)
    """
    if wacc <= g_terminal:
        raise ValueError("WACC must be greater than terminal growth rate.")
    if roic <= 0:
        raise ValueError("ROIC must be positive.")

    if roic_terminal is None:
        roic_terminal = wacc

    if roic_terminal <= g_terminal:
        raise ValueError(
            "Terminal ROIC must be greater than terminal growth rate "
            "(otherwise terminal reinvestment rate >= 1, implying negative FCF forever)."
        )

    rows = []
    pv_fcfs = 0.0
    current_nopat = nopat

    for t in range(1, years + 1):
        # Linear interpolation: year 1 → g_start, year N → g_terminal
        alpha = (t - 1) / (years - 1) if years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha

        current_nopat *= (1 + g_t)

        reinvestment_rate = g_t / roic
        reinvestment = current_nopat * reinvestment_rate
        fcf_t = current_nopat - reinvestment

        discount_factor = (1 + wacc) ** t
        pv = fcf_t / discount_factor
        pv_fcfs += pv

        rows.append({
            "Year": t,
            "Growth Rate": f"{g_t * 100:.1f}%",
            "Reinvestment Rate": f"{reinvestment_rate * 100:.1f}%",
            "NOPAT ($B)": current_nopat / 1e9,
            "Reinvestment ($B)": reinvestment / 1e9,
            "FCF ($B)": fcf_t / 1e9,
            "Discount Factor": discount_factor,
            "PV of FCF ($B)": pv / 1e9,
        })

    # Terminal value: Gordon Growth with ROIC-adjusted FCF
    terminal_reinvestment_rate = g_terminal / roic_terminal
    terminal_nopat = current_nopat * (1 + g_terminal)
    terminal_fcf = terminal_nopat * (1 - terminal_reinvestment_rate)
    terminal_value = terminal_fcf / (wacc - g_terminal)
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
        "terminal_reinvestment_rate": terminal_reinvestment_rate,
        "terminal_fcf": terminal_fcf,
        "rows": rows,
    }

