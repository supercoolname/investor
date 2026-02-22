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


# ── Core linear-growth engine ─────────────────────────────────────────────────

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

    Returns the same result dict as run_dcf.
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
    return _dcf_linear_growth(
        fcf=fcf,
        g_start=near_growth,
        g_terminal=terminal_growth,
        wacc=wacc,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        years=years,
    )


# ── Simulation ────────────────────────────────────────────────────────────────

_SIM_YEARS = 7
_SIM_NEAR_GROWTH_OFFSETS = [x / 100 for x in range(-5, 9)]   # -5% to +8% in 1% steps
_SIM_TERMINAL_GROWTH_RATES = [x / 100 for x in range(2, 9)]  # 2% to 8% in 1% steps


def run_dcf_simulation(
    fcf: float,
    near_growth: float,
    wacc: float,
    net_debt: float,
    shares_outstanding: float,
) -> dict:
    """
    Sensitivity simulation: intrinsic price across a grid of near-term growth
    start rates and terminal growth rates.

    Near-term growth varies from (near_growth - 5%) to (near_growth + 8%) in
    1% steps. Terminal growth varies from 2% to 8% in 1% steps. Forecast is
    fixed at 7 years with growth declining linearly from g_start to g_terminal.

    Args:
        fcf: Base Free Cash Flow (most recent annual, in dollars)
        near_growth: Center near-term growth rate from the DCF slider (e.g. 0.10)
        wacc: Discount rate / WACC (fixed, e.g. 0.10)
        net_debt: Total Debt - Cash (in dollars)
        shares_outstanding: Number of shares

    Returns:
        dict with keys:
            prices: 2-D list [terminal_idx][near_growth_idx] of intrinsic prices
                    (float) or None where the model is undefined (wacc ≤ g_terminal)
            near_growth_rates: list of near-term start growth rates
            terminal_growth_rates: list of terminal growth rates
    """
    near_growth_rates = [round(near_growth + d, 4) for d in _SIM_NEAR_GROWTH_OFFSETS]
    terminal_growth_rates = _SIM_TERMINAL_GROWTH_RATES

    prices = []
    for g_terminal in terminal_growth_rates:
        row = []
        for g_start in near_growth_rates:
            if wacc <= g_terminal:
                row.append(None)
                continue
            try:
                result = _dcf_linear_growth(
                    fcf=fcf,
                    g_start=g_start,
                    g_terminal=g_terminal,
                    wacc=wacc,
                    net_debt=net_debt,
                    shares_outstanding=shares_outstanding,
                    years=_SIM_YEARS,
                )
                row.append(result["intrinsic_price"])
            except (ValueError, ZeroDivisionError):
                row.append(None)
        prices.append(row)

    return {
        "prices": prices,
        "near_growth_rates": near_growth_rates,
        "terminal_growth_rates": terminal_growth_rates,
    }
