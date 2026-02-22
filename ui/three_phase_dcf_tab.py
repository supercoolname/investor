import pandas as pd
import streamlit as st

from apps.damodaran_dcf_app import (
    run_dcf_three_phase,
    compute_three_phase_sensitivity,
)
from ui.utils import fmt_b


def render_three_phase_dcf_tab():
    if "stock_data" not in st.session_state:
        st.info("Load a stock from the sidebar first.")
        return

    data = st.session_state.stock_data

    nopat = data.get("operating_cash_flow") or data["fcf"]
    nopat_source = "Operating Cash Flow" if data.get("operating_cash_flow") else "FCF (fallback)"

    # ── Phase Duration ─────────────────────────────────────────────────────────
    st.markdown("**Phase Durations (years)**")
    d1, d2, d3 = st.columns(3)
    with d1:
        years_invest = st.slider("Investment Phase", 0, 10, 3, key="tp_yi")
    with d2:
        years_scale = st.slider("Scale Phase", 0, 10, 4, key="tp_ys")
    with d3:
        years_mature = st.slider("Mature Phase", 1, 15, 5, key="tp_ym")

    total_years = years_invest + years_scale + years_mature
    st.caption(f"Total forecast: **{total_years} years**  ·  "
               f"Investment {years_invest}y → Scale {years_scale}y → Mature {years_mature}y")

    st.divider()

    # ── ROIC Inputs ────────────────────────────────────────────────────────────
    st.markdown("**ROIC by Phase**")
    r1, r2, r3 = st.columns(3)
    with r1:
        roic_invest = st.slider("ROIC — Investment (%)", 1, 30, 8, key="tp_ri") / 100
    with r2:
        roic_peak = st.slider("ROIC — Scale Peak (%)", 10, 100, 40, key="tp_rp") / 100
    with r3:
        wacc = st.slider("r — WACC (%)", 6.0, 15.0, 10.0, key="tp_r") / 100

    st.caption(
        f"Mature phase: ROIC decays linearly from **{roic_peak * 100:.0f}%** → **{wacc * 100:.1f}% (WACC)** over {years_mature}y, "
        f"eliminating terminal discontinuity."
    )

    st.divider()

    # ── Growth & Other Inputs ──────────────────────────────────────────────────
    st.markdown("**Growth & Valuation Parameters**")
    g1, g2 = st.columns(2)
    with g1:
        g_start = st.slider("g — Initial Growth (%)", 0, 100, 30, key="tp_g") / 100
    with g2:
        g_terminal = st.slider("g∞ — Terminal Growth (%)", 1.0, 4.0, 2.5, key="tp_ginf") / 100

    issuance_price = data["current_price"]
    st.caption(
        f"NOPAT proxy: **{nopat_source}** = {fmt_b(nopat)}  ·  "
        f"Terminal ROIC = WACC ({wacc * 100:.1f}%) — no excess returns in perpetuity.  ·  "
        f"⚠️ New shares assumed issued at current market price **${issuance_price:,.2f}**."
    )

    if not st.button("Calculate Intrinsic Value", type="primary", key="tp_calc"):
        return

    try:
        result = run_dcf_three_phase(
            nopat=nopat,
            roic_invest=roic_invest,
            roic_peak=roic_peak,
            g_start=g_start,
            g_terminal=g_terminal,
            wacc=wacc,
            net_debt=data["net_debt"],
            shares_outstanding=data["shares_outstanding"],
            years_invest=years_invest,
            years_scale=years_scale,
            years_mature=years_mature,
            issuance_price=issuance_price,
            roic_terminal=None,  # defaults to wacc
        )
    except ValueError as e:
        st.error(str(e))
        return

    intrinsic = result["intrinsic_price"]
    market = data["current_price"]
    margin = (intrinsic - market) / market * 100

    st.subheader(f"{data['company_name']} ({st.session_state.stock_ticker})")
    if data.get("sector") or data.get("industry"):
        st.caption(f"{data.get('sector', '')}  ·  {data.get('industry', '')}")

    # ── Key metrics ────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Intrinsic Value", f"${intrinsic:,.2f}")
    col2.metric("Current Price", f"${market:,.2f}")
    if margin >= 0:
        col3.metric("Margin of Safety", f"+{margin:.1f}%", delta="Undervalued")
    else:
        col3.metric("Margin of Safety", f"{margin:.1f}%", delta="Overvalued", delta_color="inverse")

    st.divider()

    # ── Year-by-year table ─────────────────────────────────────────────────────
    st.subheader("Year-by-Year Breakdown")
    df = pd.DataFrame(result["rows"])
    for col in ["NOPAT ($B)", "Reinvestment ($B)", "FCF ($B)",
                "Equity Raised ($B)", "Debt Raised ($B)", "PV of FCF ($B)"]:
        df[col] = df[col].map("{:.2f}".format)
    df["New Shares Issued (M)"] = df["New Shares Issued (M)"].map("{:.2f}".format)
    df["Diluted Shares (M)"] = df["Diluted Shares (M)"].map("{:.3f}".format)
    df = df.drop(columns=["Discount Factor"])

    year0 = pd.DataFrame([{
        "Year": 0,
        "Phase": "—",
        "Growth Rate": "—",
        "ROIC": "—",
        "Reinvestment Rate": "—",
        "NOPAT ($B)": f"{nopat / 1e9:.2f}",
        "Reinvestment ($B)": "—",
        "FCF ($B)": "—",
        "Equity Raised ($B)": "—",
        "Debt Raised ($B)": "—",
        "New Shares Issued (M)": "—",
        "Diluted Shares (M)": f"{data['shares_outstanding'] / 1e6:.3f}",
        "PV of FCF ($B)": "—",
    }])
    # Two illustrative terminal rows (not summed into valuation)
    terminal_rr = result["terminal_reinvestment_rate"]
    tv_nopat1 = result["terminal_nopat"]
    tv_nopat2 = tv_nopat1 * (1 + g_terminal)
    tv_rein1 = tv_nopat1 * terminal_rr
    tv_rein2 = tv_nopat2 * terminal_rr
    tv_fcf1 = result["terminal_fcf"]
    tv_fcf2 = tv_nopat2 * (1 - terminal_rr)
    n = result["total_years"]
    tv_pv1 = tv_fcf1 / (1 + wacc) ** (n + 1)
    tv_pv2 = tv_fcf2 / (1 + wacc) ** (n + 2)
    diluted_m = result["diluted_shares"] / 1e6
    terminal_rows = pd.DataFrame([
        {
            "Year": "T+1 ✦",
            "Phase": "Terminal",
            "NOPAT ($B)": f"{tv_nopat1 / 1e9:.2f}",
            "Growth Rate": f"{g_terminal * 100:.1f}%",
            "ROIC": f"{wacc * 100:.1f}%",
            "Reinvestment Rate": f"{terminal_rr * 100:.1f}%",
            "Reinvestment ($B)": f"{tv_rein1 / 1e9:.2f}",
            "FCF ($B)": f"{tv_fcf1 / 1e9:.2f}",
            "Equity Raised ($B)": "0.00",
            "Debt Raised ($B)": "0.00",
            "New Shares Issued (M)": "0.00",
            "Diluted Shares (M)": f"{diluted_m:.3f}",
            "PV of FCF ($B)": f"{tv_pv1 / 1e9:.2f}",
        },
        {
            "Year": "T+2 ✦",
            "Phase": "Terminal",
            "NOPAT ($B)": f"{tv_nopat2 / 1e9:.2f}",
            "Growth Rate": f"{g_terminal * 100:.1f}%",
            "ROIC": f"{wacc * 100:.1f}%",
            "Reinvestment Rate": f"{terminal_rr * 100:.1f}%",
            "Reinvestment ($B)": f"{tv_rein2 / 1e9:.2f}",
            "FCF ($B)": f"{tv_fcf2 / 1e9:.2f}",
            "Equity Raised ($B)": "0.00",
            "Debt Raised ($B)": "0.00",
            "New Shares Issued (M)": "0.00",
            "Diluted Shares (M)": f"{diluted_m:.3f}",
            "PV of FCF ($B)": f"{tv_pv2 / 1e9:.2f}",
        },
    ])
    df = pd.concat([year0, df, terminal_rows], ignore_index=True)
    df = df[[
        "Year", "Phase", "NOPAT ($B)", "Growth Rate", "ROIC", "Reinvestment Rate",
        "Reinvestment ($B)", "FCF ($B)",
        "Equity Raised ($B)", "Debt Raised ($B)",
        "New Shares Issued (M)", "Diluted Shares (M)", "PV of FCF ($B)",
    ]]
    st.caption("✦ Terminal rows are illustrative (individual-year FCFs, not the Gordon Growth TV sum).")
    st.dataframe(df, hide_index=True, use_container_width=True)

    # ── Summary table ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("DCF Summary")
    terminal_rr = result["terminal_reinvestment_rate"]
    summary_df = pd.DataFrame([
        (f"NOPAT₀ — Base ({nopat_source})",    fmt_b(nopat)),
        ("ROIC — Investment phase",             f"{roic_invest * 100:.1f}%"),
        ("ROIC — Scale peak",                   f"{roic_peak * 100:.1f}%"),
        ("ROIC — Terminal (= WACC)",            f"{wacc * 100:.1f}%"),
        ("g — Initial Growth Rate",             f"{g_start * 100:.1f}%"),
        ("g∞ — Terminal Growth Rate",           f"{g_terminal * 100:.1f}%"),
        ("r — WACC (Discount Rate)",            f"{wacc * 100:.1f}%"),
        ("Years — Investment / Scale / Mature", f"{years_invest} / {years_scale} / {years_mature}"),
        ("Total Forecast Years",                str(total_years)),
        ("Terminal Reinvestment Rate",          f"{terminal_rr * 100:.1f}%"),
        ("Terminal FCF",                        fmt_b(result["terminal_fcf"])),
        ("PV of FCFs",                          fmt_b(result["pv_fcfs"])),
        ("PV of Terminal Value (TV)",           fmt_b(result["pv_terminal"])),
        ("Enterprise Value (EV)",               fmt_b(result["enterprise_value"])),
        ("Net Debt",                            fmt_b(data["net_debt"])),
        ("Equity Value (EV − Net Debt)",        fmt_b(result["equity_value"])),
        ("Shares Outstanding (base)",           f"{data['shares_outstanding'] / 1e6:.2f}M"),
        ("New Shares Issued (dilution)",        f"{result['total_new_shares'] / 1e6:.2f}M"),
        ("Diluted Shares (terminal)",           f"{result['diluted_shares'] / 1e6:.2f}M"),
        ("Issuance Price (assumption)",         f"${result['issuance_price']:,.2f}"),
        ("Intrinsic Value per Share (diluted)", f"${intrinsic:.2f}"),
        ("Current Price per Share",             f"${market:.2f}"),
    ], columns=["Item", "Value"])
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    st.divider()

    # ── Sensitivity Analysis ───────────────────────────────────────────────────
    st.subheader("📊 Sensitivity Analysis")
    sens = compute_three_phase_sensitivity(
        nopat=nopat,
        roic_invest=roic_invest,
        roic_peak=roic_peak,
        g_start=g_start,
        g_terminal=g_terminal,
        wacc=wacc,
        net_debt=data["net_debt"],
        shares_outstanding=data["shares_outstanding"],
        years_invest=years_invest,
        years_scale=years_scale,
        years_mature=years_mature,
        issuance_price=issuance_price,
        roic_terminal=None,
        base_price=result["intrinsic_price"],  # reuse already-computed value
    )

    if sens:
        top3 = sens[:3]
        c1, c2, c3 = st.columns(3)
        for col, item, rank in zip([c1, c2, c3], top3, [1, 2, 3]):
            col.metric(
                f"#{rank} {item['parameter']}",
                f"{item['sensitivity']:+.1f}%",
                help="% change in intrinsic value per +1pp change in this parameter",
            )

        # Horizontal bar chart of all parameters
        sens_df = pd.DataFrame(sens).set_index("parameter")
        st.bar_chart(sens_df["sensitivity"])

        # Auto-generated interpretation based on #1 parameter
        _captions = {
            "WACC (r)":             "WACC dominates: most value sits in the terminal period — typical of high-growth companies where early FCFs are negative.",
            "Terminal Growth (g∞)": "Terminal growth dominates: the Gordon Growth spread (r − g∞) is small, so a 1pp shift amplifies dramatically.",
            "Initial Growth (g)":   "Initial growth dominates: near-term FCFs drive most of the value — typical of mature, cash-generating companies.",
            "ROIC — Scale Peak":    "Scale-phase ROIC dominates: the FCF surge during peak profitability is the core value driver.",
            "NOPAT₀":               "Base earnings dominate: NOPAT₀ scales all future FCFs proportionally — entry-point earnings are the key lever.",
            "ROIC — Investment":    "Investment-phase ROIC dominates: early capital efficiency determines how quickly the company reaches scale.",
        }
        top_param = top3[0]["parameter"]
        caption = _captions.get(top_param, f"{top_param} is the dominant value driver for this configuration.")
        st.caption(caption)

    st.divider()

    # ── Chart ──────────────────────────────────────────────────────────────────
    st.subheader("Value Breakdown")
    chart_data = pd.DataFrame({
        "Component": ["PV of FCFs", "PV of Terminal Value (TV)"],
        "Value ($B)": [result["pv_fcfs"] / 1e9, result["pv_terminal"] / 1e9],
    }).set_index("Component")
    st.bar_chart(chart_data)

    # ── Formula & Assumptions ──────────────────────────────────────────────────
    with st.expander("📐 Formula & Assumptions Used"):
        fcol, acol = st.columns([3, 2])

        with fcol:
            st.markdown("**Three-Phase ROIC DCF**")
            st.latex(r"""
                \text{ROIC}_t = \begin{cases}
                    \text{ROIC}_\text{invest} \to \text{ROIC}_\text{peak} & \text{(Investment)} \\
                    \text{ROIC}_\text{peak} & \text{(Scale)} \\
                    \text{ROIC}_\text{peak} \to r & \text{(Mature)}
                \end{cases}
            """)
            st.latex(r"""
                FCF_t = NOPAT_t \times \left(1 - \frac{g_t}{\text{ROIC}_t}\right)
            """)
            st.latex(r"""
                P = \sum_{t=1}^{N} \frac{FCF_t}{(1+r)^t}
                    + \frac{TV}{(1+r)^N}
                    - \text{Net Debt}
            """)
            st.markdown("Where:")
            st.markdown(r"""
| Symbol | Description |
|---|---|
| $\text{ROIC}_t$ | Piecewise-linear ROIC: invest → peak → WACC |
| $g_t$ | Growth, declines linearly from $g$ to $g_\infty$ across all phases |
| $TV$ | $\dfrac{FCF_N \times (1+g_\infty)}{r - g_\infty}$, with $\text{ROIC}_N = r$ |
| $r$ | WACC — Discount Rate |
| Net Debt | Total Debt − Cash & Equivalents |
""")

        with acol:
            st.markdown("**Assumptions Used**")
            for label, value in [
                (f"NOPAT₀ ({nopat_source})",        fmt_b(nopat)),
                ("ROIC — Investment phase",          f"{roic_invest * 100:.1f}%"),
                ("ROIC — Scale peak",                f"{roic_peak * 100:.1f}%"),
                ("ROIC — Terminal (= WACC)",         f"{wacc * 100:.1f}%"),
                ("g — Initial Growth Rate",          f"{g_start * 100:.1f}%"),
                ("g∞ — Terminal Growth Rate",        f"{g_terminal * 100:.1f}%"),
                ("r — WACC",                         f"{wacc * 100:.1f}%"),
                ("Years — Investment",               str(years_invest)),
                ("Years — Scale",                    str(years_scale)),
                ("Years — Mature",                   str(years_mature)),
                ("Net Debt",                         fmt_b(data["net_debt"])),
                ("Shares Outstanding",               f"{data['shares_outstanding'] / 1e9:.2f}B"),
            ]:
                st.markdown(f"- {label}: **{value}**")
