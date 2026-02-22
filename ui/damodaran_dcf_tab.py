import pandas as pd
import streamlit as st

from dcf.apps.damodaran_dcf_app import run_damodaran_dcf
from ui.utils import fmt_b


def render_damodaran_dcf_tab():
    if "stock_data" not in st.session_state:
        st.info("Load a stock from the sidebar first.")
        return

    data = st.session_state.stock_data

    # Use operating_cash_flow as NOPAT proxy (after-tax operating earnings before capex).
    # FCF already has reinvestment deducted — we need the pre-reinvestment figure.
    nopat = data.get("operating_cash_flow") or data["fcf"]
    nopat_source = "Operating Cash Flow" if data.get("operating_cash_flow") else "FCF (fallback)"

    # ── Inputs ────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        near_growth = st.slider("g — Near-term Growth (%)", 0, 30, 10, key="ddcf_g") / 100
    with c2:
        terminal_growth = st.slider("g∞ — Terminal Growth (%)", 1.0, 4.0, 2.5, key="ddcf_ginf") / 100
    with c3:
        wacc = st.slider("r — WACC (%)", 6.0, 15.0, 10.0, key="ddcf_r") / 100
    with c4:
        years = st.slider("n — Forecast Years", 3, 10, 5, key="ddcf_n")
    with c5:
        roic = st.slider("ROIC — Return on Invested Capital (%)", 5, 60, 20, key="ddcf_roic") / 100

    st.caption(
        f"NOPAT proxy: **{nopat_source}** = {fmt_b(nopat)}  ·  "
        f"Terminal ROIC defaults to WACC ({wacc * 100:.1f}%) — no excess returns in perpetuity."
    )

    if not st.button("Calculate Intrinsic Value", type="primary", key="ddcf_calc"):
        return

    try:
        result = run_damodaran_dcf(
            nopat=nopat,
            roic=roic,
            g_start=near_growth,
            g_terminal=terminal_growth,
            wacc=wacc,
            net_debt=data["net_debt"],
            shares_outstanding=data["shares_outstanding"],
            years=years,
            roic_terminal=None,  # defaults to wacc inside the model
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

    # ── Formula & Assumptions ──────────────────────────────────────────────────
    with st.expander("📐 Formula & Assumptions Used", expanded=True):
        fcol, acol = st.columns([3, 2])

        with fcol:
            st.markdown("**Damodaran ROIC-Based DCF Formula**")
            st.latex(r"""
                \text{Reinvestment Rate}_t = \frac{g_t}{\text{ROIC}}
            """)
            st.latex(r"""
                FCF_t = NOPAT_t \times \left(1 - \frac{g_t}{\text{ROIC}}\right)
            """)
            st.latex(r"""
                P = \sum_{t=1}^{n} \frac{FCF_t}{(1+r)^t}
                    + \frac{TV}{(1+r)^n}
                    - \text{Net Debt}
            """)
            st.markdown("Where:")
            st.markdown(r"""
| Symbol | Description |
|---|---|
| $NOPAT_0$ | Net Operating Profit After Tax (base year) |
| $NOPAT_t$ | $NOPAT_0 \times \prod_{s=1}^{t}(1 + g_s)$ |
| $g_t$ | Growth rate at year $t$, declines linearly from $g$ to $g_\infty$ |
| $\text{ROIC}$ | Return on Invested Capital — efficiency of growth |
| $TV$ | Terminal Value $= \dfrac{FCF_n \times (1 + g_\infty)}{r - g_\infty}$, with $\text{ROIC}_\infty = r$ |
| $r$ | WACC — Discount Rate |
| Net Debt | Total Debt − Cash & Equivalents |
""")

        with acol:
            st.markdown("**Assumptions Used in This Calculation**")
            for label, value in [
                (f"NOPAT₀ — Base ({nopat_source})", fmt_b(nopat)),
                ("ROIC — Return on Invested Capital", f"{roic * 100:.1f}%"),
                ("Terminal ROIC",                     f"{wacc * 100:.1f}% (= WACC)"),
                ("g — Near-term Growth Rate",          f"{near_growth * 100:.1f}%"),
                ("g∞ — Terminal Growth Rate",          f"{terminal_growth * 100:.1f}%"),
                ("r — WACC (Discount Rate)",           f"{wacc * 100:.1f}%"),
                ("n — Forecast Years",                 f"{years} years"),
                ("Net Debt",                           fmt_b(data['net_debt'])),
                ("Shares Outstanding",                 f"{data['shares_outstanding'] / 1e9:.2f}B"),
            ]:
                st.markdown(f"- {label}: **{value}**")

    st.divider()

    # ── Key metrics ────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Intrinsic Value", f"${intrinsic:,.2f}")
    col2.metric("Current Price", f"${market:,.2f}")
    if margin >= 0:
        col3.metric("Margin of Safety", f"+{margin:.1f}%", delta="Undervalued")
    else:
        col3.metric("Margin of Safety", f"{margin:.1f}%", delta="Overvalued", delta_color="inverse")

    st.divider()

    # ── Chart + Year-by-year table ─────────────────────────────────────────────
    col_chart, col_table = st.columns(2)

    with col_chart:
        st.subheader("Value Breakdown")
        chart_data = pd.DataFrame({
            "Component": ["PV of FCFs", "PV of Terminal Value (TV)"],
            "Value ($B)": [result["pv_fcfs"] / 1e9, result["pv_terminal"] / 1e9],
        }).set_index("Component")
        st.bar_chart(chart_data)

    with col_table:
        st.subheader("Year-by-Year Breakdown")
        df = pd.DataFrame(result["rows"])
        for col in ["NOPAT ($B)", "Reinvestment ($B)", "FCF ($B)", "PV of FCF ($B)"]:
            df[col] = df[col].map("{:.2f}".format)
        df["Discount Factor (1+r)^t"] = df["Discount Factor"].map("{:.3f}".format)
        df = df.drop(columns=["Discount Factor"])
        df = df[[
            "Year", "Growth Rate", "Reinvestment Rate",
            "NOPAT ($B)", "Reinvestment ($B)", "FCF ($B)",
            "Discount Factor (1+r)^t", "PV of FCF ($B)",
        ]]
        st.dataframe(df, hide_index=True, use_container_width=True)

    # ── Summary table ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("DCF Summary")
    terminal_rr = result["terminal_reinvestment_rate"]
    summary_df = pd.DataFrame([
        (f"NOPAT₀ — Base ({nopat_source})",    fmt_b(nopat)),
        ("ROIC — Near-term",                    f"{roic * 100:.1f}%"),
        ("ROIC — Terminal (= WACC)",            f"{wacc * 100:.1f}%"),
        ("g — Near-term Growth Rate",           f"{near_growth * 100:.1f}%"),
        ("g∞ — Terminal Growth Rate",           f"{terminal_growth * 100:.1f}%"),
        ("r — WACC (Discount Rate)",            f"{wacc * 100:.1f}%"),
        ("n — Forecast Years",                  str(years)),
        ("Terminal Reinvestment Rate",          f"{terminal_rr * 100:.1f}%"),
        ("Terminal FCF",                        fmt_b(result["terminal_fcf"])),
        ("PV of FCFs",                          fmt_b(result['pv_fcfs'])),
        ("PV of Terminal Value (TV)",           fmt_b(result['pv_terminal'])),
        ("Enterprise Value (EV)",               fmt_b(result['enterprise_value'])),
        ("Net Debt",                            fmt_b(data['net_debt'])),
        ("Equity Value (EV − Net Debt)",        fmt_b(result['equity_value'])),
        ("Shares Outstanding",                  f"{data['shares_outstanding'] / 1e9:.2f}B"),
        ("Intrinsic Value per Share",           f"${intrinsic:.2f}"),
        ("Current Price per Share",             f"${market:.2f}"),
    ], columns=["Item", "Value"])
    st.dataframe(summary_df, hide_index=True, use_container_width=True)
