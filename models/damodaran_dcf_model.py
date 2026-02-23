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

from dataclasses import dataclass
import datasource.fetcher as fetcher


@dataclass
class DFCDataYearly:
    """Raw numeric output for one forecast year. All monetary values in dollars."""
    year:              int    # global forecast year (1-indexed)
    phase:             str    # "Investment" | "Scale" | "Mature"
    g:                 float  # growth rate (e.g. 0.15)
    roic:              float  # ROIC this year (e.g. 0.30)
    reinvestment_rate: float  # g / roic
    nopat:             float  # NOPAT after growth ($)
    reinvestment:      float  # nopat × reinvestment_rate ($)
    derived_fcf:       float  # NOPAT − reinvestment ($); model-derived, not input FCF₀
    equity_raised:     float  # max(-fcf, 0) ($)
    debt_raised:       float  # always 0.0 ($)
    new_shares:        float  # equity_raised / issuance_price (count)
    shares:            float  # cumulative diluted shares (count)
    discount_factor:   float  # (1 + wacc)^year
    pv:                float  # fcf / discount_factor ($)


def resolve_nopat(data: fetcher.FinancialData) -> tuple[float, str]:
    """
    Resolve the best available NOPAT₀ from FinancialData with a fallback chain.

    Priority:
      1. EBIT × (1 − effective_tax_rate)  — correct pre-interest, after-tax earnings
      2. Operating Cash Flow              — EBIT unavailable
      3. FCF                              — last resort

    Returns:
        (nopat, nopat_source) where nopat_source is a human-readable label.
    """
    if data.nopat:
        tax_pct = f"{data.effective_tax_rate * 100:.1f}%" if data.effective_tax_rate else "N/A"
        return data.nopat, f"EBIT × (1 − {tax_pct})"
    if data.operating_cash_flow:
        return data.operating_cash_flow, "Operating Cash Flow (EBIT unavailable)"
    return data.fcf, "FCF (fallback)"


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
) -> dict:
    """
    Investment phase: ROIC ramps linearly from roic_invest → roic_peak.

    Returns:
        {
            "nopat":   float        — NOPAT at end of phase ($),
            "shares":  float        — diluted share count at end of phase,
            "pv_fcfs": float        — sum of discounted FCFs for this phase ($),
            "rows":    list[DFCDataYearly],
        }
    """
    rows: list[DFCDataYearly] = []
    pv_fcfs = 0.0

    for local_t in range(1, years_invest + 1):
        t = t_offset + local_t

        alpha_g = (t - 1) / (total_years - 1) if total_years > 1 else 1.0
        g_t = g_start + (g_terminal - g_start) * alpha_g

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

        rows.append(DFCDataYearly(
            year=t, phase="Investment",
            g=g_t, roic=roic_t, reinvestment_rate=reinvestment_rate,
            nopat=current_nopat, reinvestment=reinvestment, derived_fcf=fcf_t,
            equity_raised=equity_raised, debt_raised=0.0,
            new_shares=new_shares, shares=current_shares,
            discount_factor=discount_factor, pv=pv,
        ))

    return {"nopat": current_nopat, "shares": current_shares, "pv_fcfs": pv_fcfs, "rows": rows}


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
) -> dict:
    """
    Scale phase: ROIC is constant at roic_peak (operating leverage at full force).

    Returns:
        {"nopat", "shares", "pv_fcfs", "rows": list[DFCDataYearly]}
    """
    rows: list[DFCDataYearly] = []
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

        rows.append(DFCDataYearly(
            year=t, phase="Scale",
            g=g_t, roic=roic_t, reinvestment_rate=reinvestment_rate,
            nopat=current_nopat, reinvestment=reinvestment, derived_fcf=fcf_t,
            equity_raised=equity_raised, debt_raised=0.0,
            new_shares=new_shares, shares=current_shares,
            discount_factor=discount_factor, pv=pv,
        ))

    return {"nopat": current_nopat, "shares": current_shares, "pv_fcfs": pv_fcfs, "rows": rows}


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
) -> dict:
    """
    Mature phase: ROIC decays linearly from roic_peak → roic_terminal (= WACC).

    At the last year, roic_t = roic_terminal, so the reinvestment rate equals the
    terminal reinvestment rate — no FCF discontinuity at the forecast boundary.

    Returns:
        {"nopat", "shares", "pv_fcfs", "rows": list[DFCDataYearly]}
    """
    rows: list[DFCDataYearly] = []
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

        rows.append(DFCDataYearly(
            year=t, phase="Mature",
            g=g_t, roic=roic_t, reinvestment_rate=reinvestment_rate,
            nopat=current_nopat, reinvestment=reinvestment, derived_fcf=fcf_t,
            equity_raised=equity_raised, debt_raised=0.0,
            new_shares=new_shares, shares=current_shares,
            discount_factor=discount_factor, pv=pv,
        ))

    return {"nopat": current_nopat, "shares": current_shares, "pv_fcfs": pv_fcfs, "rows": rows}
