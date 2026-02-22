"""
Damodaran DCF application layer: public APIs for ROIC-based DCF models.
"""

from models.damodaran_dcf_model import _damodaran_dcf, _dcf_three_phase


def run_damodaran_dcf(
    nopat: float,
    roic: float,
    g_start: float,
    g_terminal: float,
    wacc: float,
    net_debt: float,
    shares_outstanding: float,
    years: int = 5,
    issuance_price: float = 0.0,
    roic_terminal: float | None = None,
) -> dict:
    """
    Public API for the Damodaran ROIC-based DCF model.

    issuance_price: share price at which new equity is issued when FCF < 0
        (assumed to be current market price). Pass 0 to skip dilution tracking.
    roic_terminal defaults to wacc (Damodaran's recommended default: no excess
        returns in perpetuity).
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
        issuance_price=issuance_price,
        roic_terminal=roic_terminal,
    )


def run_dcf_three_phase(
    nopat: float,
    roic_invest: float,
    roic_peak: float,
    g_start: float,
    g_terminal: float,
    wacc: float,
    net_debt: float,
    shares_outstanding: float,
    years_invest: int,
    years_scale: int,
    years_mature: int,
    issuance_price: float = 0.0,
    roic_terminal: float | None = None,
) -> dict:
    """
    Public API for the three-phase ROIC DCF model.

    Models high-growth company lifecycle:
      - Investment phase: low/negative ROIC, heavy capital deployment
      - Scale phase: peak ROIC, operating leverage at full force
      - Mature phase: ROIC decays linearly from peak back to roic_terminal (= WACC)

    roic_terminal defaults to wacc (no excess returns in perpetuity).
    issuance_price: share price for equity issuance when FCF < 0. Pass 0 to skip dilution.
    """
    return _dcf_three_phase(
        nopat=nopat,
        roic_invest=roic_invest,
        roic_peak=roic_peak,
        g_start=g_start,
        g_terminal=g_terminal,
        wacc=wacc,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        years_invest=years_invest,
        years_scale=years_scale,
        years_mature=years_mature,
        issuance_price=issuance_price,
        roic_terminal=roic_terminal,
    )
