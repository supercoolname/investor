"""
DCF Stock Valuation App — Streamlit UI

Key Inputs Needed for DCF Model:
+-----------------------------+-------------------------------------------------------+
| Symbol / Label              | Description                                           |
+-----------------------------+-------------------------------------------------------+
| FCF₀  Base Free Cash Flow   | Free Cash Flow = Operating Cash Flow - CapEx          |
| g     Near-term Growth Rate | e.g. 10-20% for growth stocks                         |
| g∞    Terminal Growth Rate  | e.g. 2-3% perpetual / terminal growth                 |
| r     WACC (Discount Rate)  | Weighted Avg Cost of Capital, typically 8-12%         |
|       Net Debt              | Total Debt - Cash & Equivalents                       |
|       Shares Outstanding    | From balance sheet / info                             |
+-----------------------------+-------------------------------------------------------+

Run with:
    uv run streamlit run main.py
"""

import pandas as pd
import streamlit as st

from dcf.fetcher import fetch_stock_data
from dcf.model import run_dcf
from dcf.reverse_model import run_reverse_dcf

st.set_page_config(page_title="DCF Valuation", page_icon="📈", layout="wide")

st.title("📈 DCF Stock Valuation")
st.caption("Discounted Cash Flow model powered by Yahoo Finance data")


# ── Helper formatters ──────────────────────────────────────────────────────────
def fmt_b(v):
    return f"${v / 1e9:.2f}B" if v is not None else "N/A"


def fmt_x(v):
    return f"{v:.2f}x" if v is not None else "N/A"


# ── Sidebar: Stock Lookup & Financial Data ─────────────────────────────────────
with st.sidebar:
    st.header("Stock Lookup")

    ticker = st.text_input("Ticker Symbol", value="AAPL").upper().strip()

    if st.button("Load Stock Data", type="primary", use_container_width=True):
        if not ticker:
            st.error("Please enter a ticker symbol.")
        else:
            with st.spinner(f"Fetching data for {ticker}..."):
                try:
                    st.session_state.stock_data = fetch_stock_data(ticker)
                    st.session_state.stock_ticker = ticker
                except ValueError as e:
                    st.error(str(e))

    if "stock_data" in st.session_state:
        data = st.session_state.stock_data
        loaded_ticker = st.session_state.stock_ticker

        if ticker != loaded_ticker:
            st.caption(f"⚠ Showing data for {loaded_ticker}. Click Load to refresh.")

        st.divider()

        st.markdown(f"**{data['company_name']}** ({loaded_ticker})")
        if data.get("sector") or data.get("industry"):
            st.caption(f"{data.get('sector', '')}  ·  {data.get('industry', '')}")

        st.divider()

        st.markdown("**Cash Flow Statement**")
        st.markdown(f"- Op CF: **{fmt_b(data.get('operating_cash_flow'))}**")
        st.markdown(f"- CapEx: **{fmt_b(data.get('capex'))}**")
        st.markdown(f"- FCF₀: **{fmt_b(data['fcf'])}**")

        st.markdown("**Balance Sheet**")
        st.markdown(f"- Total Debt: **{fmt_b(data['total_debt'])}**")
        st.markdown(f"- Cash: **{fmt_b(data['cash'])}**")
        st.markdown(f"- Net Debt: **{fmt_b(data['net_debt'])}**")
        st.markdown(f"- Shares: **{data['shares_outstanding'] / 1e9:.2f}B**")

        st.markdown("**Market Data**")
        st.markdown(f"- Price: **${data['current_price']:,.2f}**")
        st.markdown(f"- Mkt Cap: **{fmt_b(data.get('market_cap'))}**")
        st.markdown(f"- Revenue: **{fmt_b(data.get('revenue'))}**")
        st.markdown(f"- EBITDA: **{fmt_b(data.get('ebitda'))}**")
        st.markdown(f"- P/E: **{fmt_x(data.get('pe_ratio'))}**")


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_dcf, tab_reverse = st.tabs(["📈 DCF Valuation", "🔄 Reverse DCF"])

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 1: Standard DCF
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dcf:
    if "stock_data" not in st.session_state:
        st.info("Load a stock from the sidebar first.")
    else:
        data = st.session_state.stock_data

        # ── Inline controls ────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            near_growth = st.slider("g — Near-term Growth Rate (%)", 0, 30, 10, key="dcf_g") / 100
        with c2:
            terminal_growth = st.slider("g∞ — Terminal Growth Rate (%)", 1.0, 4.0, 2.5, key="dcf_ginf") / 100
        with c3:
            wacc = st.slider("r — WACC / Discount Rate (%)", 6.0, 15.0, 10.0, key="dcf_r") / 100
        with c4:
            years = st.slider("n — Forecast Years", 3, 10, 5, key="dcf_n")

        if st.button("Calculate Intrinsic Value", type="primary", key="dcf_calc"):
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
                st.stop()

            intrinsic = result["intrinsic_price"]
            market = data["current_price"]
            margin = (intrinsic - market) / market * 100

            st.subheader(f"{data['company_name']} ({st.session_state.stock_ticker})")
            if data.get("sector") or data.get("industry"):
                st.caption(f"{data.get('sector', '')}  ·  {data.get('industry', '')}")

            # ── Formula & Assumptions ──────────────────────────────────────────
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
| $FCF_t$ | $FCF_0 \times (1 + g)^t$ — projected Free Cash Flow in year $t$ |
| $g$ | Near-term Growth Rate |
| $TV$ | Terminal Value $= \dfrac{FCF_n \times (1 + g_\infty)}{r - g_\infty}$ |
| $g_\infty$ | Terminal Growth Rate (perpetual) |
| $r$ | WACC — Discount Rate |
| $n$ | Forecast Years |
| Net Debt | Total Debt − Cash & Equivalents |
""")

                with acol:
                    st.markdown("**Assumptions Used in This Calculation**")
                    assumptions = [
                        ("FCF₀ — Base Free Cash Flow",    fmt_b(data['fcf'])),
                        ("g — Near-term Growth Rate",      f"{near_growth * 100:.1f}%"),
                        ("g∞ — Terminal Growth Rate",      f"{terminal_growth * 100:.1f}%"),
                        ("r — WACC (Discount Rate)",       f"{wacc * 100:.1f}%"),
                        ("n — Forecast Years",             f"{years} years"),
                        ("Net Debt",                       fmt_b(data['net_debt'])),
                        ("Shares Outstanding",             f"{data['shares_outstanding'] / 1e9:.2f}B"),
                    ]
                    for label, value in assumptions:
                        st.markdown(f"- {label}: **{value}**")

            st.divider()

            # ── Key metrics ────────────────────────────────────────────────────
            col1, col2, col3 = st.columns(3)
            col1.metric("Intrinsic Value", f"${intrinsic:,.2f}")
            col2.metric("Current Price", f"${market:,.2f}")

            if margin >= 0:
                col3.metric("Margin of Safety", f"+{margin:.1f}%", delta="Undervalued")
            else:
                col3.metric("Margin of Safety", f"{margin:.1f}%", delta="Overvalued", delta_color="inverse")

            st.divider()

            # ── Chart + Year-by-year table ─────────────────────────────────────
            col_chart, col_table = st.columns([1, 1])

            with col_chart:
                st.subheader("Value Breakdown")
                chart_data = pd.DataFrame({
                    "Component": ["PV of FCFs", "PV of Terminal Value (TV)"],
                    "Value ($B)": [
                        result["pv_fcfs"] / 1e9,
                        result["pv_terminal"] / 1e9,
                    ],
                }).set_index("Component")
                st.bar_chart(chart_data)

            with col_table:
                st.subheader("Year-by-Year FCF Breakdown")
                df = pd.DataFrame(result["rows"])
                df["Projected FCF ($B)"] = df["Projected FCF ($B)"].map("{:.2f}".format)
                df["Discount Factor (1+r)^t"] = df["Discount Factor"].map("{:.3f}".format)
                df["PV of FCF ($B)"] = df["PV of FCF ($B)"].map("{:.2f}".format)
                df = df.drop(columns=["Discount Factor"])
                st.dataframe(df, hide_index=True, use_container_width=True)

            # ── Summary table ──────────────────────────────────────────────────
            st.divider()
            st.subheader("DCF Summary")
            summary = [
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
            ]
            summary_df = pd.DataFrame(summary, columns=["Item", "Value"])
            st.dataframe(summary_df, hide_index=True, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 2: Reverse DCF
# ═══════════════════════════════════════════════════════════════════════════════
with tab_reverse:
    st.caption(
        "Given the current market price, what growth rate and discount rate is the market implying?"
    )

    if "stock_data" not in st.session_state:
        st.info("Load a stock from the sidebar first.")
    else:
        rdata = st.session_state.stock_data

        # ── Inline controls ────────────────────────────────────────────────────
        rc1, rc2, rc3, rc4 = st.columns(4)
        with rc1:
            rdcf_terminal_growth = st.slider(
                "g∞ — Terminal Growth Rate (%)", 1.0, 4.0, 2.5, key="rdcf_g_inf"
            ) / 100
        with rc2:
            rdcf_wacc = st.slider(
                "r — WACC / Discount Rate (%)", 6.0, 15.0, 10.0, key="rdcf_wacc"
            ) / 100
        with rc3:
            rdcf_near_growth = st.slider(
                "g — Near-term Growth Assumption (%)", 0, 30, 10, key="rdcf_g"
            ) / 100
        with rc4:
            rdcf_years = st.slider("n — Forecast Years", 3, 10, 5, key="rdcf_years")

        if st.button("Calculate Implied Rates", type="primary", key="rdcf_calc"):
            if rdata["fcf"] <= 0:
                st.warning(
                    f"FCF₀ is negative (${rdata['fcf'] / 1e9:.2f}B). "
                    "Reverse DCF may not converge for companies with negative free cash flow."
                )

            try:
                rresult = run_reverse_dcf(
                    fcf=rdata["fcf"],
                    wacc=rdcf_wacc,
                    near_growth=rdcf_near_growth,
                    terminal_growth=rdcf_terminal_growth,
                    net_debt=rdata["net_debt"],
                    shares_outstanding=rdata["shares_outstanding"],
                    years=rdcf_years,
                    current_price=rdata["current_price"],
                )
            except Exception as e:
                st.error(f"Reverse DCF calculation failed: {e}")
                st.stop()

            implied_g = rresult["implied_g"]
            implied_r = rresult["implied_r"]
            market = rdata["current_price"]

            st.subheader(f"{rdata['company_name']} ({st.session_state.stock_ticker})")
            if rdata.get("sector") or rdata.get("industry"):
                st.caption(f"{rdata.get('sector', '')}  ·  {rdata.get('industry', '')}")

            # ── Key metrics ────────────────────────────────────────────────────
            m1, m2, m3 = st.columns(3)
            m1.metric(
                "Implied g — Near-term Growth Rate",
                f"{implied_g * 100:.2f}%" if implied_g is not None else "N/A",
                help="Growth rate that makes DCF intrinsic value = current market price (r held fixed)"
            )
            m2.metric(
                "Implied r — WACC / Discount Rate",
                f"{implied_r * 100:.2f}%" if implied_r is not None else "N/A",
                help="Discount rate that makes DCF intrinsic value = current market price (g held fixed)"
            )
            m3.metric("Current Market Price", f"${market:,.2f}")

            if implied_g is None:
                st.warning(
                    "Could not solve for Implied g. The current price may be outside the range "
                    "achievable by any growth rate in [-50%, 100%] at the given WACC."
                )
            if implied_r is None:
                st.warning(
                    "Could not solve for Implied r. The current price may be outside the range "
                    "achievable by any discount rate in [g∞+0.1%, 50%] at the given growth rate."
                )

            if implied_g is not None:
                st.info(
                    f"The market expects **{rdata['company_name']}** FCF₀ to grow at "
                    f"**{implied_g * 100:.1f}%/yr** for {rdcf_years} years "
                    f"(assuming r = {rdcf_wacc * 100:.1f}% and g∞ = {rdcf_terminal_growth * 100:.1f}%) "
                    f"to justify a price of **${market:,.2f}**."
                )

            st.divider()

            # ── Formula & Assumptions expander ────────────────────────────────
            with st.expander("📐 Reverse DCF Formula & Assumptions", expanded=False):
                fcol, acol = st.columns([3, 2])

                with fcol:
                    st.markdown("**Reverse DCF — Solving for Implied g**")
                    st.latex(r"""
                        P_{\text{market}} = \sum_{t=1}^{n} \frac{FCF_0 \cdot (1+g)^t}{(1+r)^t}
                            + \frac{TV(g)}{(1+r)^n}
                            - \text{Net Debt}^*
                    """)
                    st.caption("*Net Debt divided by Shares Outstanding")
                    st.markdown(
                        "Given the current market price $P_{\\text{market}}$, we numerically solve for "
                        "$g$ (near-term growth) such that the DCF formula produces the market price. "
                        "Uses `scipy.optimize.brentq` — bracketed root-finding over $g \\in [-50\\%, 100\\%]$."
                    )

                with acol:
                    st.markdown("**Assumptions Used**")
                    assumptions_r = [
                        ("FCF₀ — Base Free Cash Flow",     fmt_b(rdata['fcf'])),
                        ("g∞ — Terminal Growth Rate",       f"{rdcf_terminal_growth * 100:.1f}%"),
                        ("r — WACC (held fixed for Implied g)", f"{rdcf_wacc * 100:.1f}%"),
                        ("g — Near-term (held fixed for Implied r)", f"{rdcf_near_growth * 100:.1f}%"),
                        ("n — Forecast Years",              f"{rdcf_years} years"),
                        ("Net Debt",                        fmt_b(rdata['net_debt'])),
                        ("Shares Outstanding",              f"{rdata['shares_outstanding'] / 1e9:.2f}B"),
                        ("Current Market Price",            f"${market:,.2f}"),
                    ]
                    for label, value in assumptions_r:
                        st.markdown(f"- {label}: **{value}**")

            # ── Sensitivity table ──────────────────────────────────────────────
            st.subheader("Sensitivity: Implied g across WACC values")
            st.caption("Implied near-term growth rate (g) for r ± 2% in 0.5% steps (g∞ and n held fixed)")

            r_deltas = [-0.020, -0.015, -0.010, -0.005, 0.000, 0.005, 0.010, 0.015, 0.020]
            sens_rows = []
            for delta in r_deltas:
                r_test = rdcf_wacc + delta
                if r_test <= rdcf_terminal_growth:
                    sens_rows.append({
                        "r (WACC)": f"{r_test * 100:.1f}%",
                        "Implied g": "N/A (r ≤ g∞)",
                    })
                    continue
                try:
                    sens = run_reverse_dcf(
                        fcf=rdata["fcf"],
                        wacc=r_test,
                        near_growth=rdcf_near_growth,
                        terminal_growth=rdcf_terminal_growth,
                        net_debt=rdata["net_debt"],
                        shares_outstanding=rdata["shares_outstanding"],
                        years=rdcf_years,
                        current_price=market,
                    )
                    g_val = sens["implied_g"]
                    label = f"{g_val * 100:.2f}%" if g_val is not None else "N/A"
                    if delta == 0.0:
                        label = f"**{label}** ← selected r"
                except Exception:
                    label = "error"

                sens_rows.append({
                    "r (WACC)": f"{r_test * 100:.1f}%",
                    "Implied g": label,
                })

            sens_df = pd.DataFrame(sens_rows)
            st.dataframe(sens_df, hide_index=True, use_container_width=True)

        else:
            st.caption(
                "r is held fixed to solve for Implied g · g is held fixed to solve for Implied r"
            )
