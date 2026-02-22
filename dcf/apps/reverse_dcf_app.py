"""
Reverse DCF: given the current market price, solve for the implied near-term
growth rate (g) that the market is pricing in.

This answers: "What must this company grow at to justify its current price?"

Uses scipy.optimize.brentq for bracketed root-finding (stable & fast).
"""

from scipy.optimize import brentq

from dcf.models.dcf_model import _dcf_linear_growth


def solve_implied_g(
    fcf: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    years: int,
    current_price: float,
) -> float | None:
    """
    Solve for the implied near-term growth rate (g) given the current market price.

    Holds wacc, terminal_growth, and years fixed; searches g ∈ [-50%, 100%].

    Args:
        fcf: Base Free Cash Flow (most recent annual, in dollars)
        wacc: Discount rate / WACC (fixed, e.g. 0.10)
        terminal_growth: Perpetual terminal growth rate (fixed, e.g. 0.025)
        net_debt: Total Debt - Cash (in dollars)
        shares_outstanding: Number of shares
        years: Near-term forecast horizon
        current_price: Current market price per share

    Returns:
        Implied near-term growth rate as a float, or None if no solution found.
    """

    def price_error(g: float) -> float:
        try:
            result = _dcf_linear_growth(
                fcf=fcf,
                g_start=g,
                g_terminal=terminal_growth,
                wacc=wacc,
                net_debt=net_debt,
                shares_outstanding=shares_outstanding,
                years=years,
            )
            return result["intrinsic_price"] - current_price
        except ValueError:
            return float("nan")

    try:
        fa = price_error(-0.50)
        fb = price_error(1.00)
        if fa * fb < 0:
            return brentq(price_error, -0.50, 1.00, xtol=1e-6, maxiter=200)
    except (ValueError, RuntimeError):
        pass

    return None
