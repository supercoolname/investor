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


def compute_three_phase_sensitivity(
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
) -> list[dict]:
    """
    Compute % sensitivity of intrinsic_price to each continuous input parameter.

    Each rate/ROIC/growth parameter is perturbed by +1pp (+0.01 absolute).
    nopat is perturbed by +1% relative (since it is in dollars, not a rate).

    Returns a list of {"parameter": str, "sensitivity": float} dicts, sorted by
    abs(sensitivity) descending — most impactful parameter first.

    Perturbations that violate model constraints (e.g. g_terminal >= wacc) are
    silently skipped.
    """
    base_args = dict(
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
    base_price = run_dcf_three_phase(**base_args)["intrinsic_price"]

    perturbations = [
        ("WACC (r)",             {"wacc": wacc + 0.01}),
        ("Initial Growth (g)",   {"g_start": g_start + 0.01}),
        ("Terminal Growth (g∞)", {"g_terminal": g_terminal + 0.01}),
        ("ROIC — Investment",    {"roic_invest": roic_invest + 0.01}),
        ("ROIC — Scale Peak",    {"roic_peak": roic_peak + 0.01}),
        ("NOPAT₀",               {"nopat": nopat * 1.01}),
    ]

    results = []
    for label, override in perturbations:
        try:
            perturbed_price = run_dcf_three_phase(**{**base_args, **override})["intrinsic_price"]
            sensitivity = (perturbed_price - base_price) / base_price * 100
            results.append({"parameter": label, "sensitivity": sensitivity})
        except ValueError:
            pass  # skip invalid perturbations (e.g. g_terminal + 0.01 >= wacc)

    return sorted(results, key=lambda x: abs(x["sensitivity"]), reverse=True)
