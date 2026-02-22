import pandas as pd
import streamlit as st

import apps.damodaran_dcf_app as damodaran_dcf_app
import datasource.fetcher as fetcher
import ui.utils as utils


def _render_stock_info(data, ticker: str):
    st.markdown(f"**{data.company_name}** ({ticker})")
    if data.sector or data.industry:
        st.caption(f"{data.sector or ''}  ·  {data.industry or ''}")

    st.markdown("**Income Statement**")
    st.markdown(f"- EBIT: **{utils.fmt_b(data.ebit)}**")
    tax_str = f"{data.effective_tax_rate * 100:.1f}%" if data.effective_tax_rate else "N/A"
    st.markdown(f"- Eff. Tax Rate: **{tax_str}**")
    st.markdown(f"- NOPAT: **{utils.fmt_b(data.nopat)}**")

    st.markdown("**Cash Flow Statement**")
    st.markdown(f"- Op CF: **{utils.fmt_b(data.operating_cash_flow)}**")
    st.markdown(f"- CapEx: **{utils.fmt_b(data.capex)}**")
    st.markdown(f"- SBC: **{utils.fmt_b(data.sbc)}**")
    st.markdown(f"- FCF₀: **{utils.fmt_b(data.fcf)}**")

    st.markdown("**Balance Sheet**")
    st.markdown(f"- Total Debt: **{utils.fmt_b(data.total_debt)}**")
    st.markdown(f"- Cash: **{utils.fmt_b(data.cash)}**")
    st.markdown(f"- Net Debt: **{utils.fmt_b(data.net_debt)}**")
    st.markdown(f"- Shares: **{data.shares_outstanding / 1e9:.2f}B**")

    st.markdown("**Market Data**")
    st.markdown(f"- Price: **${data.current_price:,.2f}**")
    st.markdown(f"- Mkt Cap: **{utils.fmt_b(data.market_cap)}**")
    st.markdown(f"- Revenue: **{utils.fmt_b(data.revenue)}**")
    st.markdown(f"- EBITDA: **{utils.fmt_b(data.ebitda)}**")
    st.markdown(f"- P/E: **{utils.fmt_x(data.pe_ratio)}**")


def render_three_phase_dcf_tab():
    tc, bc = st.columns([3, 1])
    with tc:
        ticker = st.text_input("Ticker Symbol", value="AAPL", key="tp_ticker_input").upper().strip()
    with bc:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        load = st.button("Load", type="primary", key="tp_load", use_container_width=True)

    if load and ticker:
        with st.spinner(f"Fetching {ticker}..."):
            try:
                st.session_state.tp_stock_data = fetcher.fetch_stock_data(ticker)
                st.session_state.tp_stock_ticker = ticker
            except ValueError as e:
                st.error(str(e))
                return

    if "tp_stock_data" not in st.session_state:
        st.info("Enter a ticker and click Load.")
        return

    data = st.session_state.tp_stock_data
    loaded_ticker = st.session_state.tp_stock_ticker

    if data.nopat:
        nopat = data.nopat
        tax_pct = f"{data.effective_tax_rate * 100:.1f}%" if data.effective_tax_rate else "N/A"
        nopat_source = f"EBIT × (1 − {tax_pct})"
    elif data.operating_cash_flow:
        nopat = data.operating_cash_flow
        nopat_source = "Operating Cash Flow (EBIT unavailable)"
    else:
        nopat = data.fcf
        nopat_source = "FCF (fallback)"

    # ── Two-column layout: inputs left, stock data right ───────────────────────
    left, right = st.columns([2, 1])

    with right:
        _render_stock_info(data, loaded_ticker)

    with left:
        # ── Phase Duration ──────────────────────────────────────────────────────
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

        # ── ROIC Inputs ─────────────────────────────────────────────────────────
        st.markdown("**ROIC by Phase**")
        r1, r2, r3 = st.columns(3)
        with r1:
            roic_invest = st.slider("ROIC — Investment (%)", 1, 30, 8, key="tp_ri") / 100
        with r2:
            roic_peak = st.slider("ROIC — Scale Peak (%)", 10, 100, 40, key="tp_rp") / 100
        with r3:
            wacc = st.slider("r — WACC (%)", 6.0, 15.0, 10.0, key="tp_r") / 100

        st.caption(
            f"Mature phase: ROIC decays linearly from **{roic_peak * 100:.0f}%** → "
            f"**{wacc * 100:.1f}% (WACC)** over {years_mature}y, eliminating terminal discontinuity."
        )

        st.divider()

        # ── Growth & Other Inputs ───────────────────────────────────────────────
        st.markdown("**Growth & Valuation Parameters**")
        g1, g2 = st.columns(2)
        with g1:
            g_start = st.slider("g — Initial Growth (%)", 0, 100, 30, key="tp_g") / 100
        with g2:
            g_terminal = st.slider("g∞ — Terminal Growth (%)", 1.0, 4.0, 2.5, key="tp_ginf") / 100

        issuance_price = data.current_price
        st.caption(
            f"NOPAT proxy: **{nopat_source}** = {utils.fmt_b(nopat)}  ·  "
            f"Terminal ROIC = WACC ({wacc * 100:.1f}%) — no excess returns in perpetuity.  ·  "
            f"⚠️ New shares assumed issued at current market price **${issuance_price:,.2f}**."
        )

        calc_clicked = st.button("Calculate Intrinsic Value", type="primary", key="tp_calc")

    if not calc_clicked:
        return

    # ── Results (full width) ───────────────────────────────────────────────────
    try:
        result = damodaran_dcf_app.run_dcf_three_phase(
            nopat=nopat,
            roic_invest=roic_invest,
            roic_peak=roic_peak,
            g_start=g_start,
            g_terminal=g_terminal,
            wacc=wacc,
            net_debt=data.net_debt,
            shares_outstanding=data.shares_outstanding,
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
    market = data.current_price
    margin = (intrinsic - market) / market * 100

    st.subheader(f"{data.company_name} ({loaded_ticker})")
    if data.sector or data.industry:
        st.caption(f"{data.sector or ''}  ·  {data.industry or ''}")

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
    for col in ["NOPAT ($B)", "Reinvestment ($B)", "Derived FCF ($B)",
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
        "Derived FCF ($B)": "—",
        "Equity Raised ($B)": "—",
        "Debt Raised ($B)": "—",
        "New Shares Issued (M)": "—",
        "Diluted Shares (M)": f"{data.shares_outstanding / 1e6:.3f}",
        "PV of FCF ($B)": "—",
    }])
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
            "Derived FCF ($B)": f"{tv_fcf1 / 1e9:.2f}",
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
            "Derived FCF ($B)": f"{tv_fcf2 / 1e9:.2f}",
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
        "Reinvestment ($B)", "Derived FCF ($B)",
        "Equity Raised ($B)", "Debt Raised ($B)",
        "New Shares Issued (M)", "Diluted Shares (M)", "PV of FCF ($B)",
    ]]
    st.caption("✦ Terminal rows are illustrative (individual-year values, not the Gordon Growth TV sum).  Derived FCF = NOPAT − Reinvestment (model output; not input FCF₀).")
    st.dataframe(df, hide_index=True, use_container_width=True)

    # ── Summary table ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("DCF Summary")
    terminal_rr = result["terminal_reinvestment_rate"]
    summary_df = pd.DataFrame([
        (f"NOPAT₀ — Base ({nopat_source})",    utils.fmt_b(nopat)),
        ("ROIC — Investment phase",             f"{roic_invest * 100:.1f}%"),
        ("ROIC — Scale peak",                   f"{roic_peak * 100:.1f}%"),
        ("ROIC — Terminal (= WACC)",            f"{wacc * 100:.1f}%"),
        ("g — Initial Growth Rate",             f"{g_start * 100:.1f}%"),
        ("g∞ — Terminal Growth Rate",           f"{g_terminal * 100:.1f}%"),
        ("r — WACC (Discount Rate)",            f"{wacc * 100:.1f}%"),
        ("Years — Investment / Scale / Mature", f"{years_invest} / {years_scale} / {years_mature}"),
        ("Total Forecast Years",                str(total_years)),
        ("Terminal Reinvestment Rate",          f"{terminal_rr * 100:.1f}%"),
        ("Terminal FCF",                        utils.fmt_b(result["terminal_fcf"])),
        ("PV of FCFs",                          utils.fmt_b(result["pv_fcfs"])),
        ("PV of Terminal Value (TV)",           utils.fmt_b(result["pv_terminal"])),
        ("Enterprise Value (EV)",               utils.fmt_b(result["enterprise_value"])),
        ("Net Debt",                            utils.fmt_b(data.net_debt)),
        ("Equity Value (EV − Net Debt)",        utils.fmt_b(result["equity_value"])),
        ("Shares Outstanding (base)",           f"{data.shares_outstanding / 1e6:.2f}M"),
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
    sens = damodaran_dcf_app.compute_three_phase_sensitivity(
        nopat=nopat,
        roic_invest=roic_invest,
        roic_peak=roic_peak,
        g_start=g_start,
        g_terminal=g_terminal,
        wacc=wacc,
        net_debt=data.net_debt,
        shares_outstanding=data.shares_outstanding,
        years_invest=years_invest,
        years_scale=years_scale,
        years_mature=years_mature,
        issuance_price=issuance_price,
        roic_terminal=None,
        base_price=result["intrinsic_price"],
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

        sens_df = pd.DataFrame(sens).set_index("parameter")
        st.bar_chart(sens_df["sensitivity"])

        _captions = {
            "WACC (r)":             "WACC dominates: most value sits in the terminal period — typical of high-growth companies where early FCFs are negative.",
            "Terminal Growth (g∞)": "Terminal growth dominates: the Gordon Growth spread (r − g∞) is small, so a 1pp shift amplifies dramatically.",
            "Initial Growth (g)":   "Initial growth dominates: near-term FCFs drive most of the value — typical of mature, cash-generating companies.",
            "ROIC — Scale Peak":    "Scale-phase ROIC dominates: the FCF surge during peak profitability is the core value driver.",
            "NOPAT₀":               "Base earnings dominate: NOPAT₀ scales all future FCFs proportionally — entry-point earnings are the key lever.",
            "ROIC — Investment":    "Investment-phase ROIC dominates: early capital efficiency determines how quickly the company reaches scale.",
        }
        top_param = top3[0]["parameter"]
        st.caption(_captions.get(top_param, f"{top_param} is the dominant value driver for this configuration."))

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
                \text{Derived FCF}_t = NOPAT_t \times \left(1 - \frac{g_t}{\text{ROIC}_t}\right)
            """)
            st.latex(r"""
                P = \sum_{t=1}^{N} \frac{\text{Derived FCF}_t}{(1+r)^t}
                    + \frac{TV}{(1+r)^N}
                    - \text{Net Debt}
            """)
            st.markdown("Where:")
            st.markdown(r"""
| Symbol | Description |
|---|---|
| $\text{ROIC}_t$ | Piecewise-linear ROIC: invest → peak → WACC |
| $g_t$ | Growth, declines linearly from $g$ to $g_\infty$ across all phases |
| $\text{Derived FCF}_t$ | NOPAT$_t$ − Reinvestment$_t$ (model-derived; ≠ input FCF₀) |
| $TV$ | $\dfrac{\text{Derived FCF}_N \times (1+g_\infty)}{r - g_\infty}$, with $\text{ROIC}_N = r$ |
| $r$ | WACC — Discount Rate |
| Net Debt | Total Debt − Cash & Equivalents |
""")

        with acol:
            st.markdown("**Assumptions Used**")
            for label, value in [
                (f"NOPAT₀ ({nopat_source})",        utils.fmt_b(nopat)),
                ("ROIC — Investment phase",          f"{roic_invest * 100:.1f}%"),
                ("ROIC — Scale peak",                f"{roic_peak * 100:.1f}%"),
                ("ROIC — Terminal (= WACC)",         f"{wacc * 100:.1f}%"),
                ("g — Initial Growth Rate",          f"{g_start * 100:.1f}%"),
                ("g∞ — Terminal Growth Rate",        f"{g_terminal * 100:.1f}%"),
                ("r — WACC",                         f"{wacc * 100:.1f}%"),
                ("Years — Investment",               str(years_invest)),
                ("Years — Scale",                    str(years_scale)),
                ("Years — Mature",                   str(years_mature)),
                ("Net Debt",                         utils.fmt_b(data.net_debt)),
                ("Shares Outstanding",               f"{data.shares_outstanding / 1e9:.2f}B"),
            ]:
                st.markdown(f"- {label}: **{value}**")
