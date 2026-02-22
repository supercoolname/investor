"""
Damodaran DCF application layer: public API for the ROIC-based DCF model.
"""

from models.damodaran_dcf_model import _damodaran_dcf


def run_damodaran_dcf(
    nopat: float,
    roic: float,
    g_start: float,
    g_terminal: float,
    wacc: float,
    net_debt: float,
    shares_outstanding: float,
    years: int = 5,
    roic_terminal: float | None = None,
) -> dict:
    """
    Public API for the Damodaran ROIC-based DCF model.

    roic_terminal defaults to wacc (Damodaran's recommended default: no excess
    returns in perpetuity). Pass an explicit value to model a sustainably
    advantaged business in the terminal period.
    """
    return _damodaran_dcf(
        nopat=nopat,
        roic=roic,
        g_start=g_start,
        g_terminal=g_terminal,
        wacc=wacc,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        years=years,
        roic_terminal=roic_terminal,
    )
