"""
Damodaran ROIC-based DCF models.

Growth requires reinvestment. Each year:
    reinvestment_rate = g_t / roic_t
    FCF_t             = NOPAT_t × (1 − reinvestment_rate)

When FCF_t < 0 (g_t > roic_t), the company must raise external capital. All additional
capital is assumed to come from equity issuance at `issuance_price` (current market
price), which dilutes existing shareholders.

When roic → ∞: degenerates to simple FCF growth (no reinvestment needed).
When roic = wacc: growth adds zero excess value (competitive equilibrium).
When roic < wacc: growth destroys value.

Terminal value uses roic_terminal (defaults to wacc per Damodaran — no excess
returns in perpetuity under competition).

Three-phase model: invest (low ROIC) → scale (peak ROIC) → mature (ROIC decays to WACC)
"""


def _phase_investment(
    current_nopat: float,
    current_shares: float,
    t_offset: int,
    years_invest: int,
    roic_invest: float,
    roic_peak: float,
    g_start: float,
    g_terminal: float,
    total_years: int,
    wacc: float,
    issuance_price: float,
) -> tuple[float, float, float, list[dict]]:
    """
    Investment phase: ROIC ramps linearly from roic_invest → roic_peak.

    Args:
        current_nopat:  NOPAT at end of prior phase (year t_offset base value).
        current_shares: Share count entering this phase.
        t_offset:       Global year index of the last completed year before this phase.
        years_invest:   Number of years in this phase.
        roic_invest:    ROIC at the first year of this phase.
        roic_peak:      ROIC target at the end of this phase (reached in Scale).
        g_start, g_terminal, total_years: Global growth interpolation parameters.
        wacc:           Discount rate.
        issuance_price: Share price for equity issuance (0 = skip dilution).

    Returns:
        (current_nopat, current_shares, pv_fcfs, rows) after this phase.
    """
    rows = []
    pv_fcfs = 0.0

    for local_t in range(1, years_invest + 1):
        t = t_offset + local_t

        alpha_g = (t - 1) / (total_years - 1) if total_years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha_g

        # ROIC: 0 at local_t=1 (start of phase), approaching roic_peak
        alpha_r = (local_t - 1) / years_invest
        roic_t = roic_invest + (roic_peak - roic_invest) * alpha_r

        current_nopat *= (1 + g_t)
        reinvestment_rate = g_t / roic_t
        reinvestment = current_nopat * reinvestment_rate
        fcf_t = current_nopat - reinvestment

        equity_raised = max(-fcf_t, 0.0)
        new_shares = equity_raised / issuance_price if issuance_price > 0 else 0.0
        current_shares += new_shares

        discount_factor = (1 + wacc) ** t
        pv = fcf_t / discount_factor
        pv_fcfs += pv

        rows.append({
            "Year": t,
            "Phase": "Investment",
            "Growth Rate": f"{g_t * 100:.1f}%",
            "ROIC": f"{roic_t * 100:.1f}%",
            "Reinvestment Rate": f"{reinvestment_rate * 100:.1f}%",
            "NOPAT ($B)": current_nopat / 1e9,
            "Reinvestment ($B)": reinvestment / 1e9,
            "FCF ($B)": fcf_t / 1e9,
            "Equity Raised ($B)": equity_raised / 1e9,
            "Debt Raised ($B)": 0.0,
            "New Shares Issued (M)": new_shares / 1e6,
            "Diluted Shares (M)": current_shares / 1e6,
            "Discount Factor": discount_factor,
            "PV of FCF ($B)": pv / 1e9,
        })

    return current_nopat, current_shares, pv_fcfs, rows


def _phase_scale(
    current_nopat: float,
    current_shares: float,
    t_offset: int,
    years_scale: int,
    roic_peak: float,
    g_start: float,
    g_terminal: float,
    total_years: int,
    wacc: float,
    issuance_price: float,
) -> tuple[float, float, float, list[dict]]:
    """
    Scale phase: ROIC is constant at roic_peak (operating leverage at full force).

    Args:
        current_nopat:  NOPAT at end of prior phase.
        current_shares: Share count entering this phase.
        t_offset:       Global year index of the last completed year before this phase.
        years_scale:    Number of years in this phase.
        roic_peak:      ROIC throughout this phase (constant).
        g_start, g_terminal, total_years: Global growth interpolation parameters.
        wacc:           Discount rate.
        issuance_price: Share price for equity issuance (0 = skip dilution).

    Returns:
        (current_nopat, current_shares, pv_fcfs, rows) after this phase.
    """
    rows = []
    pv_fcfs = 0.0

    for local_t in range(1, years_scale + 1):
        t = t_offset + local_t

        alpha_g = (t - 1) / (total_years - 1) if total_years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha_g

        roic_t = roic_peak

        current_nopat *= (1 + g_t)
        reinvestment_rate = g_t / roic_t
        reinvestment = current_nopat * reinvestment_rate
        fcf_t = current_nopat - reinvestment

        equity_raised = max(-fcf_t, 0.0)
        new_shares = equity_raised / issuance_price if issuance_price > 0 else 0.0
        current_shares += new_shares

        discount_factor = (1 + wacc) ** t
        pv = fcf_t / discount_factor
        pv_fcfs += pv

        rows.append({
            "Year": t,
            "Phase": "Scale",
            "Growth Rate": f"{g_t * 100:.1f}%",
            "ROIC": f"{roic_t * 100:.1f}%",
            "Reinvestment Rate": f"{reinvestment_rate * 100:.1f}%",
            "NOPAT ($B)": current_nopat / 1e9,
            "Reinvestment ($B)": reinvestment / 1e9,
            "FCF ($B)": fcf_t / 1e9,
            "Equity Raised ($B)": equity_raised / 1e9,
            "Debt Raised ($B)": 0.0,
            "New Shares Issued (M)": new_shares / 1e6,
            "Diluted Shares (M)": current_shares / 1e6,
            "Discount Factor": discount_factor,
            "PV of FCF ($B)": pv / 1e9,
        })

    return current_nopat, current_shares, pv_fcfs, rows


def _phase_mature(
    current_nopat: float,
    current_shares: float,
    t_offset: int,
    years_mature: int,
    roic_peak: float,
    roic_terminal: float,
    g_start: float,
    g_terminal: float,
    total_years: int,
    wacc: float,
    issuance_price: float,
) -> tuple[float, float, float, list[dict]]:
    """
    Mature phase: ROIC decays linearly from roic_peak → roic_terminal (= WACC).

    This guarantees no FCF discontinuity at the forecast/terminal boundary:
    at the last mature year, roic_t = roic_terminal, so the reinvestment rate
    equals the terminal reinvestment rate exactly.

    Args:
        current_nopat:  NOPAT at end of prior phase.
        current_shares: Share count entering this phase.
        t_offset:       Global year index of the last completed year before this phase.
        years_mature:   Number of years in this phase.
        roic_peak:      ROIC at the start of this phase (first year = roic_peak).
        roic_terminal:  ROIC at the end of this phase (last year = roic_terminal).
        g_start, g_terminal, total_years: Global growth interpolation parameters.
        wacc:           Discount rate.
        issuance_price: Share price for equity issuance (0 = skip dilution).

    Returns:
        (current_nopat, current_shares, pv_fcfs, rows) after this phase.
    """
    rows = []
    pv_fcfs = 0.0

    for local_t in range(1, years_mature + 1):
        t = t_offset + local_t

        alpha_g = (t - 1) / (total_years - 1) if total_years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha_g

        alpha_r = (local_t - 1) / (years_mature - 1) if years_mature > 1 else 1.0
        roic_t = roic_peak + (roic_terminal - roic_peak) * alpha_r

        current_nopat *= (1 + g_t)
        reinvestment_rate = g_t / roic_t
        reinvestment = current_nopat * reinvestment_rate
        fcf_t = current_nopat - reinvestment

        equity_raised = max(-fcf_t, 0.0)
        new_shares = equity_raised / issuance_price if issuance_price > 0 else 0.0
        current_shares += new_shares

        discount_factor = (1 + wacc) ** t
        pv = fcf_t / discount_factor
        pv_fcfs += pv

        rows.append({
            "Year": t,
            "Phase": "Mature",
            "Growth Rate": f"{g_t * 100:.1f}%",
            "ROIC": f"{roic_t * 100:.1f}%",
            "Reinvestment Rate": f"{reinvestment_rate * 100:.1f}%",
            "NOPAT ($B)": current_nopat / 1e9,
            "Reinvestment ($B)": reinvestment / 1e9,
            "FCF ($B)": fcf_t / 1e9,
            "Equity Raised ($B)": equity_raised / 1e9,
            "Debt Raised ($B)": 0.0,
            "New Shares Issued (M)": new_shares / 1e6,
            "Diluted Shares (M)": current_shares / 1e6,
            "Discount Factor": discount_factor,
            "PV of FCF ($B)": pv / 1e9,
        })

    return current_nopat, current_shares, pv_fcfs, rows


def _dcf_three_phase(
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
    Three-phase ROIC DCF reflecting the lifecycle of high-growth companies.

    Delegates each phase to a dedicated function:
      _phase_investment — ROIC ramps roic_invest → roic_peak
      _phase_scale      — ROIC constant at roic_peak
      _phase_mature     — ROIC decays roic_peak → roic_terminal (= WACC)

    Growth declines linearly from g_start → g_terminal across all years,
    regardless of phase boundaries.

    Returns:
        intrinsic_price, enterprise_value, equity_value,
        pv_fcfs, pv_terminal, terminal_reinvestment_rate, terminal_fcf,
        diluted_shares, total_new_shares, issuance_price, total_years,
        rows (year-by-year breakdown with Phase and ROIC columns)
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

    current_nopat = nopat
    current_shares = shares_outstanding

    current_nopat, current_shares, pv1, rows1 = _phase_investment(
        current_nopat, current_shares, t_offset=0,
        years_invest=years_invest,
        roic_invest=roic_invest, roic_peak=roic_peak,
        g_start=g_start, g_terminal=g_terminal, total_years=total_years,
        wacc=wacc, issuance_price=issuance_price,
    )
    current_nopat, current_shares, pv2, rows2 = _phase_scale(
        current_nopat, current_shares, t_offset=years_invest,
        years_scale=years_scale,
        roic_peak=roic_peak,
        g_start=g_start, g_terminal=g_terminal, total_years=total_years,
        wacc=wacc, issuance_price=issuance_price,
    )
    current_nopat, current_shares, pv3, rows3 = _phase_mature(
        current_nopat, current_shares, t_offset=years_invest + years_scale,
        years_mature=years_mature,
        roic_peak=roic_peak, roic_terminal=roic_terminal,
        g_start=g_start, g_terminal=g_terminal, total_years=total_years,
        wacc=wacc, issuance_price=issuance_price,
    )

    rows = rows1 + rows2 + rows3
    pv_fcfs = pv1 + pv2 + pv3

    # Terminal value: Gordon Growth with ROIC-adjusted FCF
    # roic_t at last mature year = roic_terminal, so no discontinuity
    terminal_reinvestment_rate = g_terminal / roic_terminal
    terminal_nopat = current_nopat * (1 + g_terminal)
    terminal_fcf = terminal_nopat * (1 - terminal_reinvestment_rate)
    terminal_value = terminal_fcf / (wacc - g_terminal)
    pv_terminal = terminal_value / (1 + wacc) ** total_years

    enterprise_value = pv_fcfs + pv_terminal
    equity_value = enterprise_value - net_debt
    intrinsic_price = equity_value / current_shares

    total_new_shares = current_shares - shares_outstanding

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
        "diluted_shares": current_shares,
        "total_new_shares": total_new_shares,
        "issuance_price": issuance_price,
        "rows": rows,
    }
