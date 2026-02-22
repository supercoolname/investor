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

Two model variants:
  _damodaran_dcf      — single near-term ROIC, fixed throughout forecast
  _dcf_three_phase    — piecewise ROIC: invest (low) → scale (peak) → mature (decay to WACC)
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
    issuance_price: float = 0.0,
    roic_terminal: float | None = None,
) -> dict:
    """
    DCF where growth is funded by reinvestment scaled by ROIC. When FCF < 0,
    the shortfall is raised as equity, diluting the share count.

    Args:
        nopat: Base-year Net Operating Profit After Tax ($)
        roic: Near-term Return on Invested Capital (e.g. 0.20 for 20%)
        g_start: Near-term growth rate at year 1 (e.g. 0.15)
        g_terminal: Perpetual terminal growth rate (e.g. 0.025)
        wacc: Discount rate / WACC (e.g. 0.10)
        net_debt: Total Debt - Cash ($)
        shares_outstanding: Number of shares (base, pre-dilution)
        years: Forecast horizon
        issuance_price: Share price at which new equity is issued ($).
            Assumed to be current market price. When 0 or not provided,
            dilution is not computed (new shares = 0).
        roic_terminal: ROIC in terminal period. Defaults to wacc (zero excess
            returns in perpetuity — Damodaran's recommended default).

    Returns:
        dict with keys:
            intrinsic_price, enterprise_value, equity_value,
            pv_fcfs, pv_terminal, terminal_reinvestment_rate, terminal_fcf,
            diluted_shares, total_new_shares, issuance_price,
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
    current_shares = shares_outstanding

    for t in range(1, years + 1):
        # Linear interpolation: year 1 → g_start, year N → g_terminal
        alpha = (t - 1) / (years - 1) if years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha

        current_nopat *= (1 + g_t)

        # Growth = ROIC × Reinvestment Rate
        reinvestment_rate = g_t / roic
        reinvestment = current_nopat * reinvestment_rate
        fcf_t = current_nopat - reinvestment

        # External capital: all from equity when FCF < 0
        equity_raised = max(-fcf_t, 0.0)
        debt_raised = 0.0

        if issuance_price > 0:
            new_shares = equity_raised / issuance_price
        else:
            new_shares = 0.0
        current_shares += new_shares

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
            "Equity Raised ($B)": equity_raised / 1e9,
            "Debt Raised ($B)": debt_raised / 1e9,
            "New Shares Issued (M)": new_shares / 1e6,
            "Diluted Shares (M)": current_shares / 1e6,
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
    intrinsic_price = equity_value / current_shares   # diluted share count

    total_new_shares = current_shares - shares_outstanding

    return {
        "intrinsic_price": intrinsic_price,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "pv_fcfs": pv_fcfs,
        "pv_terminal": pv_terminal,
        "terminal_reinvestment_rate": terminal_reinvestment_rate,
        "terminal_fcf": terminal_fcf,
        "diluted_shares": current_shares,
        "total_new_shares": total_new_shares,
        "issuance_price": issuance_price,
        "rows": rows,
    }


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
    Three-phase ROIC DCF reflecting the lifecycle of high-growth companies:

    Phase 1 — Investment: ROIC starts low (heavy capex, negative margins).
        ROIC interpolates linearly from roic_invest toward roic_peak.
    Phase 2 — Scale: Operating leverage kicks in. ROIC stays at roic_peak.
    Phase 3 — Mature: Competition erodes excess returns. ROIC decays linearly
        from roic_peak back to roic_terminal (= WACC), guaranteeing no
        discontinuity at the forecast/terminal boundary.

    Growth rate declines linearly from g_start → g_terminal across all years,
    regardless of phase boundaries.

    When FCF < 0 (growth > ROIC), the shortfall is raised as equity at
    issuance_price, diluting the share count.

    Args:
        nopat: Base-year NOPAT ($)
        roic_invest: ROIC at start of investment phase (e.g. 0.05 for 5%)
        roic_peak: Peak ROIC during scale phase (e.g. 0.40 for 40%)
        g_start: Initial growth rate (e.g. 0.30)
        g_terminal: Perpetual terminal growth rate (e.g. 0.025)
        wacc: Discount rate / WACC
        net_debt: Total Debt - Cash ($)
        shares_outstanding: Base share count (pre-dilution)
        years_invest: Number of years in investment phase
        years_scale: Number of years in scale phase
        years_mature: Number of years in mature phase
        issuance_price: Share price for equity issuance when FCF < 0.
            Pass 0 to skip dilution tracking.
        roic_terminal: ROIC at end of mature phase and in perpetuity.
            Defaults to wacc (Damodaran's recommended default).

    Returns:
        Same keys as _damodaran_dcf:
            intrinsic_price, enterprise_value, equity_value,
            pv_fcfs, pv_terminal, terminal_reinvestment_rate, terminal_fcf,
            diluted_shares, total_new_shares, issuance_price,
            rows (year-by-year breakdown, each row has "Phase" and "ROIC" fields)
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

    rows = []
    pv_fcfs = 0.0
    current_nopat = nopat
    current_shares = shares_outstanding

    for t in range(1, total_years + 1):
        # Growth: linear across all phases
        alpha_g = (t - 1) / (total_years - 1) if total_years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha_g

        # ROIC: piecewise linear across three phases
        if t <= years_invest:
            # Investment phase: roic_invest → approaching roic_peak
            alpha_r = (t - 1) / years_invest  # 0 at t=1; (n-1)/n at t=years_invest
            roic_t = roic_invest + (roic_peak - roic_invest) * alpha_r
            phase = "Investment"
        elif t <= years_invest + years_scale:
            # Scale phase: locked at peak
            roic_t = roic_peak
            phase = "Scale"
        else:
            # Mature phase: roic_peak → roic_terminal
            t_m = t - years_invest - years_scale  # local index 1 … years_mature
            alpha_r = (t_m - 1) / (years_mature - 1) if years_mature > 1 else 1.0
            roic_t = roic_peak + (roic_terminal - roic_peak) * alpha_r
            phase = "Mature"

        current_nopat *= (1 + g_t)

        reinvestment_rate = g_t / roic_t
        reinvestment = current_nopat * reinvestment_rate
        fcf_t = current_nopat - reinvestment

        equity_raised = max(-fcf_t, 0.0)
        debt_raised = 0.0

        if issuance_price > 0:
            new_shares = equity_raised / issuance_price
        else:
            new_shares = 0.0
        current_shares += new_shares

        discount_factor = (1 + wacc) ** t
        pv = fcf_t / discount_factor
        pv_fcfs += pv

        rows.append({
            "Year": t,
            "Phase": phase,
            "Growth Rate": f"{g_t * 100:.1f}%",
            "ROIC": f"{roic_t * 100:.1f}%",
            "Reinvestment Rate": f"{reinvestment_rate * 100:.1f}%",
            "NOPAT ($B)": current_nopat / 1e9,
            "Reinvestment ($B)": reinvestment / 1e9,
            "FCF ($B)": fcf_t / 1e9,
            "Equity Raised ($B)": equity_raised / 1e9,
            "Debt Raised ($B)": debt_raised / 1e9,
            "New Shares Issued (M)": new_shares / 1e6,
            "Diluted Shares (M)": current_shares / 1e6,
            "Discount Factor": discount_factor,
            "PV of FCF ($B)": pv / 1e9,
        })

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
        "terminal_fcf": terminal_fcf,
        "diluted_shares": current_shares,
        "total_new_shares": total_new_shares,
        "issuance_price": issuance_price,
        "rows": rows,
    }
