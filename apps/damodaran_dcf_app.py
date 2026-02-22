"""
Damodaran DCF application layer: public APIs for ROIC-based DCF models.

Formatting boundary: model functions (_phase_*) return raw numeric dicts.
This layer converts raw rows to display format before returning to callers.
"""

from models.damodaran_dcf_model import (
    _phase_investment,
    _phase_scale,
    _phase_mature,
)


def _format_rows(raw_rows: list[dict]) -> list[dict]:
    """
    Convert raw numeric model rows to display-ready rows.

    Rates (g, roic, reinvestment_rate) → "15.0%" strings.
    Dollar amounts → float $B.
    Share counts → float M.
    """
    return [
        {
            "Year":                   row["year"],
            "Phase":                  row["phase"],
            "Growth Rate":            f"{row['g'] * 100:.1f}%",
            "ROIC":                   f"{row['roic'] * 100:.1f}%",
            "Reinvestment Rate":      f"{row['reinvestment_rate'] * 100:.1f}%",
            "NOPAT ($B)":             row["nopat"] / 1e9,
            "Reinvestment ($B)":      row["reinvestment"] / 1e9,
            "FCF ($B)":               row["fcf"] / 1e9,
            "Equity Raised ($B)":     row["equity_raised"] / 1e9,
            "Debt Raised ($B)":       row["debt_raised"] / 1e9,
            "New Shares Issued (M)":  row["new_shares"] / 1e6,
            "Diluted Shares (M)":     row["shares"] / 1e6,
            "Discount Factor":        row["discount_factor"],
            "PV of FCF ($B)":         row["pv"] / 1e9,
        }
        for row in raw_rows
    ]


# ── Per-phase public APIs ──────────────────────────────────────────────────────
#
# Each function accepts the state carried in from the prior phase
# (nopat, current_shares) and the global growth-interpolation context
# (g_start, g_terminal, total_years), then returns the updated state together
# with the phase's FCF PV contribution and display-ready rows.
#
# Return schema (all three): {"nopat", "shares", "pv_fcfs", "rows"}


def run_phase_investment(
    nopat: float,
    current_shares: float,
    t_offset: int,
    years_invest: int,
    roic_invest: float,
    roic_peak: float,
    g_start: float,
    g_terminal: float,
    total_years: int,
    wacc: float,
    issuance_price: float = 0.0,
) -> dict:
    """
    Investment phase: ROIC ramps linearly from roic_invest → roic_peak.

    Args:
        nopat:          Base NOPAT entering this phase ($).
        current_shares: Share count entering this phase.
        t_offset:       Last completed global year before this phase (0 if first).
        years_invest:   Number of years in this phase.
        roic_invest:    ROIC at the first year of this phase.
        roic_peak:      ROIC target at the end of this phase.
        g_start, g_terminal, total_years: Global growth interpolation context.
        wacc:           Discount rate.
        issuance_price: Equity issuance price when FCF < 0 (0 = skip dilution).

    Returns:
        {"nopat": float, "shares": float, "pv_fcfs": float, "rows": list[dict]}
        where rows are display-ready (rates as "x.x%", amounts as $B, shares as M).
    """
    phase = _phase_investment(
        current_nopat=nopat,
        current_shares=current_shares,
        t_offset=t_offset,
        years_invest=years_invest,
        roic_invest=roic_invest,
        roic_peak=roic_peak,
        g_start=g_start,
        g_terminal=g_terminal,
        total_years=total_years,
        wacc=wacc,
        issuance_price=issuance_price,
    )
    return {
        "nopat":   phase["nopat"],
        "shares":  phase["shares"],
        "pv_fcfs": phase["pv_fcfs"],
        "rows":    _format_rows(phase["rows"]),
    }


def run_phase_scale(
    nopat: float,
    current_shares: float,
    t_offset: int,
    years_scale: int,
    roic_peak: float,
    g_start: float,
    g_terminal: float,
    total_years: int,
    wacc: float,
    issuance_price: float = 0.0,
) -> dict:
    """
    Scale phase: ROIC is constant at roic_peak (operating leverage at full force).

    Args:
        nopat:          NOPAT at end of investment phase.
        current_shares: Share count entering this phase.
        t_offset:       Last completed global year (= years_invest).
        years_scale:    Number of years in this phase.
        roic_peak:      ROIC throughout this phase.
        g_start, g_terminal, total_years: Global growth interpolation context.
        wacc:           Discount rate.
        issuance_price: Equity issuance price when FCF < 0 (0 = skip dilution).

    Returns:
        {"nopat": float, "shares": float, "pv_fcfs": float, "rows": list[dict]}
    """
    phase = _phase_scale(
        current_nopat=nopat,
        current_shares=current_shares,
        t_offset=t_offset,
        years_scale=years_scale,
        roic_peak=roic_peak,
        g_start=g_start,
        g_terminal=g_terminal,
        total_years=total_years,
        wacc=wacc,
        issuance_price=issuance_price,
    )
    return {
        "nopat":   phase["nopat"],
        "shares":  phase["shares"],
        "pv_fcfs": phase["pv_fcfs"],
        "rows":    _format_rows(phase["rows"]),
    }


def run_phase_mature(
    nopat: float,
    current_shares: float,
    t_offset: int,
    years_mature: int,
    roic_peak: float,
    roic_terminal: float,
    g_start: float,
    g_terminal: float,
    total_years: int,
    wacc: float,
    issuance_price: float = 0.0,
) -> dict:
    """
    Mature phase: ROIC decays linearly from roic_peak → roic_terminal (= WACC).

    Guarantees no FCF discontinuity at the forecast/terminal boundary: at the
    last mature year, roic_t = roic_terminal, matching the terminal reinvestment
    rate exactly.

    Args:
        nopat:          NOPAT at end of scale phase.
        current_shares: Share count entering this phase.
        t_offset:       Last completed global year (= years_invest + years_scale).
        years_mature:   Number of years in this phase.
        roic_peak:      ROIC at the first year of this phase.
        roic_terminal:  ROIC at the last year of this phase (and in perpetuity).
        g_start, g_terminal, total_years: Global growth interpolation context.
        wacc:           Discount rate.
        issuance_price: Equity issuance price when FCF < 0 (0 = skip dilution).

    Returns:
        {"nopat": float, "shares": float, "pv_fcfs": float, "rows": list[dict]}
    """
    phase = _phase_mature(
        current_nopat=nopat,
        current_shares=current_shares,
        t_offset=t_offset,
        years_mature=years_mature,
        roic_peak=roic_peak,
        roic_terminal=roic_terminal,
        g_start=g_start,
        g_terminal=g_terminal,
        total_years=total_years,
        wacc=wacc,
        issuance_price=issuance_price,
    )
    return {
        "nopat":   phase["nopat"],
        "shares":  phase["shares"],
        "pv_fcfs": phase["pv_fcfs"],
        "rows":    _format_rows(phase["rows"]),
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────


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
    Orchestrates the three-phase ROIC DCF by calling run_phase_investment,
    run_phase_scale, and run_phase_mature in sequence, then computing the
    Gordon Growth terminal value and final equity valuation.

    roic_terminal defaults to wacc (no excess returns in perpetuity).
    issuance_price: share price for equity issuance when FCF < 0. Pass 0 to skip dilution.
    """
    total_years = years_invest + years_scale + years_mature
    if total_years < 1:
        raise ValueError("Total forecast years must be at least 1.")
    if wacc <= g_terminal:
        raise ValueError("WACC must be greater than terminal growth rate.")
    if roic_invest <= 0:
        raise ValueError("roic_invest must be positive.")
    if roic_peak <= 0:
        raise ValueError("roic_peak must be positive.")
    if roic_terminal is None:
        roic_terminal = wacc
    if roic_terminal <= g_terminal:
        raise ValueError(
            "Terminal ROIC must be greater than terminal growth rate "
            "(otherwise terminal reinvestment rate >= 1, implying negative FCF forever)."
        )

    common = dict(
        g_start=g_start, g_terminal=g_terminal,
        total_years=total_years, wacc=wacc, issuance_price=issuance_price,
    )

    phase1 = run_phase_investment(
        nopat=nopat, current_shares=shares_outstanding, t_offset=0,
        years_invest=years_invest, roic_invest=roic_invest, roic_peak=roic_peak,
        **common,
    )
    phase2 = run_phase_scale(
        nopat=phase1["nopat"], current_shares=phase1["shares"], t_offset=years_invest,
        years_scale=years_scale, roic_peak=roic_peak,
        **common,
    )
    phase3 = run_phase_mature(
        nopat=phase2["nopat"], current_shares=phase2["shares"],
        t_offset=years_invest + years_scale,
        years_mature=years_mature, roic_peak=roic_peak, roic_terminal=roic_terminal,
        **common,
    )

    rows = phase1["rows"] + phase2["rows"] + phase3["rows"]
    pv_fcfs = phase1["pv_fcfs"] + phase2["pv_fcfs"] + phase3["pv_fcfs"]
    final_nopat = phase3["nopat"]
    final_shares = phase3["shares"]

    terminal_reinvestment_rate = g_terminal / roic_terminal
    terminal_nopat = final_nopat * (1 + g_terminal)
    terminal_fcf = terminal_nopat * (1 - terminal_reinvestment_rate)
    terminal_value = terminal_fcf / (wacc - g_terminal)
    pv_terminal = terminal_value / (1 + wacc) ** total_years

    enterprise_value = pv_fcfs + pv_terminal
    equity_value = enterprise_value - net_debt
    intrinsic_price = equity_value / final_shares

    return {
        "intrinsic_price": intrinsic_price,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "pv_fcfs": pv_fcfs,
        "pv_terminal": pv_terminal,
        "terminal_reinvestment_rate": terminal_reinvestment_rate,
        "terminal_nopat": terminal_nopat,
        "terminal_fcf": terminal_fcf,
        "total_years": total_years,
        "diluted_shares": final_shares,
        "total_new_shares": final_shares - shares_outstanding,
        "issuance_price": issuance_price,
        "rows": rows,
    }


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
    base_price: float | None = None,
) -> list[dict]:
    """
    Compute % sensitivity of intrinsic_price to each continuous input parameter.

    Each rate/ROIC/growth parameter is perturbed by +1pp (+0.01 absolute).
    nopat is perturbed by +1% relative (since it is in dollars, not a rate).

    base_price: pre-computed intrinsic_price from the caller's base run. If None,
        the base case is computed internally. Pass result["intrinsic_price"] to
        avoid a redundant model evaluation.

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
    if base_price is None:
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
