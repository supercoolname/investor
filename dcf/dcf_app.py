"""
DCF application layer: public API for running DCF valuations and simulations.
"""

from dcf.dcf_model import _dcf_linear_growth

_SIM_YEARS = 7
_SIM_NEAR_GROWTH_OFFSETS = [x / 100 for x in range(-5, 9)]   # -5% to +8% in 1% steps
_SIM_TERMINAL_GROWTH_RATES = [x / 100 for x in range(2, 9)]  # 2% to 8% in 1% steps


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
    Runs the DCF model and returns a full breakdown of results.

    Growth declines linearly from near_growth (year 1) to terminal_growth
    (year `years`), then continues at terminal_growth in perpetuity.

    Args:
        fcf: Base Free Cash Flow (most recent annual, in dollars)
        near_growth: Near-term growth rate at year 1 (e.g. 0.10 for 10%)
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
