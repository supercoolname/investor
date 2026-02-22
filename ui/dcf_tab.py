import pandas as pd
import streamlit as st

from dcf.dcf_app import run_dcf, run_dcf_simulation
from ui.utils import fmt_b


def render_dcf_tab():
    if "stock_data" not in st.session_state:
        st.info("Load a stock from the sidebar first.")
        return

    data = st.session_state.stock_data

    # ── Inputs ────────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        near_growth = st.slider("g — Near-term Growth Rate (%)", 0, 30, 10, key="dcf_g") / 100
    with c2:
        terminal_growth = st.slider("g∞ — Terminal Growth Rate (%)", 1.0, 4.0, 2.5, key="dcf_ginf") / 100
    with c3:
        wacc = st.slider("r — WACC / Discount Rate (%)", 6.0, 15.0, 10.0, key="dcf_r") / 100
    with c4:
        years = st.slider("n — Forecast Years", 3, 10, 5, key="dcf_n")

    if not st.button("Calculate Intrinsic Value", type="primary", key="dcf_calc"):
        return

    try:
        result = run_dcf(
            fcf=data["fcf"],
            near_growth=near_growth,
            wacc=wacc,
            terminal_growth=terminal_growth,
            net_debt=data["net_debt"],
            shares_outstanding=data["shares_outstanding"],
            years=years,
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
            st.markdown("**DCF Formula**")
            st.latex(r"""
                P = \sum_{t=1}^{n} \frac{FCF_t}{(1+r)^t}
                    + \frac{TV}{(1+r)^n}
                    - \text{Net Debt}
            """)
            st.markdown("Where:")
            st.markdown(r"""
| Symbol | Description |
|---|---|
| $FCF_0$ | Base Free Cash Flow (most recent annual) |
| $FCF_t$ | $FCF_0 \times (1 + g_t)$ — projected FCF in year $t$, $g_t$ declines linearly |
| $g$ | Near-term Growth Rate (year 1) |
| $TV$ | Terminal Value $= \dfrac{FCF_n \times (1 + g_\infty)}{r - g_\infty}$ |
| $g_\infty$ | Terminal Growth Rate (perpetual) |
| $r$ | WACC — Discount Rate |
| $n$ | Forecast Years |
| Net Debt | Total Debt − Cash & Equivalents |
""")

        with acol:
            st.markdown("**Assumptions Used in This Calculation**")
            for label, value in [
                ("FCF₀ — Base Free Cash Flow",    fmt_b(data['fcf'])),
                ("g — Near-term Growth Rate",      f"{near_growth * 100:.1f}%"),
                ("g∞ — Terminal Growth Rate",      f"{terminal_growth * 100:.1f}%"),
                ("r — WACC (Discount Rate)",       f"{wacc * 100:.1f}%"),
                ("n — Forecast Years",             f"{years} years"),
                ("Net Debt",                       fmt_b(data['net_debt'])),
                ("Shares Outstanding",             f"{data['shares_outstanding'] / 1e9:.2f}B"),
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
        st.subheader("Year-by-Year FCF Breakdown")
        df = pd.DataFrame(result["rows"])
        df["Projected FCF ($B)"] = df["Projected FCF ($B)"].map("{:.2f}".format)
        df["Discount Factor (1+r)^t"] = df["Discount Factor"].map("{:.3f}".format)
        df["PV of FCF ($B)"] = df["PV of FCF ($B)"].map("{:.2f}".format)
        df = df.drop(columns=["Discount Factor"])
        df = df[["Year", "Growth Rate", "Projected FCF ($B)", "Discount Factor (1+r)^t", "PV of FCF ($B)"]]
        st.dataframe(df, hide_index=True, use_container_width=True)

    # ── Summary table ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("DCF Summary")
    summary_df = pd.DataFrame([
        ("FCF₀ — Base Free Cash Flow",         fmt_b(data['fcf'])),
        ("g — Near-term Growth Rate",           f"{near_growth * 100:.1f}%"),
        ("g∞ — Terminal Growth Rate",           f"{terminal_growth * 100:.1f}%"),
        ("r — WACC (Discount Rate)",            f"{wacc * 100:.1f}%"),
        ("n — Forecast Years",                  str(years)),
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

    # ── Simulation table ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Valuation Sensitivity (Linear Growth Simulation)")
    st.caption(
        f"Intrinsic value per share across near-term growth start rates "
        f"({near_growth * 100 - 5:.0f}% – {near_growth * 100 + 8:.0f}%) "
        f"and terminal growth rates (2% – 8%), declining linearly over 7 years. "
        f"r = {wacc * 100:.1f}% held fixed. "
        f"Green = above market price (${market:,.2f}), red = below."
    )

    sim = run_dcf_simulation(
        fcf=data["fcf"],
        near_growth=near_growth,
        wacc=wacc,
        net_debt=data["net_debt"],
        shares_outstanding=data["shares_outstanding"],
    )

    sim_df = pd.DataFrame(
        [[f"${p:,.0f}" if p is not None else "N/A" for p in row] for row in sim["prices"]],
        index=[f"{r * 100:.0f}%" for r in sim["terminal_growth_rates"]],
        columns=[f"{r * 100:.0f}%" for r in sim["near_growth_rates"]],
    )
    sim_df.index.name = "g∞ \\ g start →"

    def _color(val):
        if val == "N/A":
            return "color: gray"
        try:
            price = float(val.replace("$", "").replace(",", ""))
        except ValueError:
            return ""
        return "background-color: #d4edda; color: #155724" if price >= market else "background-color: #f8d7da; color: #721c24"

    st.dataframe(sim_df.style.applymap(_color), use_container_width=True)
