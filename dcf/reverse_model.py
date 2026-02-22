"""
Reverse DCF: given the current market price, solve for the implied near-term
growth rate (g) or implied WACC (r) that the market is pricing in.

This answers: "What must this company grow at to justify its current price?"

Uses scipy.optimize.brentq for bracketed root-finding (stable & fast).
"""

from scipy.optimize import brentq

from dcf.model import run_dcf


def run_reverse_dcf(
    fcf: float,
    wacc: float,
    near_growth: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    years: int,
    current_price: float,
) -> dict:
    """
    Solves for the implied growth rate and implied WACC given the current market price.

    - implied_g: fix wacc, terminal_growth, years → brentq over g ∈ [-50%, 100%]
    - implied_r: fix near_growth, terminal_growth, years → brentq over r ∈ (terminal_growth+0.1%, 50%]

    Args:
        fcf: Base Free Cash Flow (most recent annual, in dollars)
        wacc: Fixed discount rate used when solving for implied_g (e.g. 0.10)
        near_growth: Fixed growth rate used when solving for implied_r (e.g. 0.10)
        terminal_growth: Perpetual terminal growth rate (e.g. 0.025)
        net_debt: Total Debt - Cash (in dollars)
        shares_outstanding: Number of shares
        years: Forecast horizon
        current_price: Current market price per share

    Returns:
        dict with keys: implied_g (float or None), implied_r (float or None)
    """

    def price_given_g(g: float) -> float:
        try:
            result = run_dcf(
                fcf=fcf,
                near_growth=g,
                wacc=wacc,
                terminal_growth=terminal_growth,
                net_debt=net_debt,
                shares_outstanding=shares_outstanding,
                years=years,
            )
            return result["intrinsic_price"] - current_price
        except ValueError:
            return float("nan")

    def price_given_r(r: float) -> float:
        try:
            result = run_dcf(
                fcf=fcf,
                near_growth=near_growth,
                wacc=r,
                terminal_growth=terminal_growth,
                net_debt=net_debt,
                shares_outstanding=shares_outstanding,
                years=years,
            )
            return result["intrinsic_price"] - current_price
        except ValueError:
            return float("nan")

    # Solve for implied_g: search g in [-50%, 100%]
    implied_g = None
    try:
        fa = price_given_g(-0.50)
        fb = price_given_g(1.00)
        if fa * fb < 0:
            implied_g = brentq(price_given_g, -0.50, 1.00, xtol=1e-6, maxiter=200)
    except (ValueError, RuntimeError):
        implied_g = None

    # Solve for implied_r: search r in (terminal_growth + 0.1%, 50%]
    implied_r = None
    r_lo = terminal_growth + 0.001
    r_hi = 0.50
    try:
        fa = price_given_r(r_lo)
        fb = price_given_r(r_hi)
        if fa * fb < 0:
            implied_r = brentq(price_given_r, r_lo, r_hi, xtol=1e-6, maxiter=200)
    except (ValueError, RuntimeError):
        implied_r = None

    return {"implied_g": implied_g, "implied_r": implied_r}
