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

st.set_page_config(page_title="DCF Valuation", page_icon="📈", layout="wide")

st.title("📈 DCF Stock Valuation")
st.caption("Discounted Cash Flow model powered by Yahoo Finance data")

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")

    ticker = st.text_input("Ticker Symbol", value="AAPL").upper().strip()

    st.subheader("Growth Assumptions")
    near_growth = st.slider("g — Near-term Growth Rate (%)", 0, 30, 10) / 100
    terminal_growth = st.slider("g∞ — Terminal Growth Rate (%)", 1.0, 4.0, 2.5) / 100

    st.subheader("Discount Rate")
    wacc = st.slider("r — WACC / Discount Rate (%)", 6.0, 15.0, 10.0) / 100

    st.subheader("Forecast")
    years = st.slider("n — Forecast Years", 3, 10, 5)

    calculate = st.button("Calculate Intrinsic Value", type="primary", use_container_width=True)

# ── Main content ──────────────────────────────────────────────────────────────
if calculate:
    if not ticker:
        st.error("Please enter a ticker symbol.")
    else:
        with st.spinner(f"Fetching data for {ticker}..."):
            try:
                data = fetch_stock_data(ticker)
            except ValueError as e:
                st.error(str(e))
                st.stop()

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

        st.subheader(f"{data['company_name']} ({ticker})")
        if data.get("sector") or data.get("industry"):
            st.caption(f"{data.get('sector', '')}  ·  {data.get('industry', '')}")

        # ── Raw data used for DCF ─────────────────────────────────────────────
        with st.expander("📊 Raw Data Used for DCF (from Yahoo Finance)", expanded=True):
            d1, d2, d3 = st.columns(3)

            def fmt_b(v):
                return f"${v / 1e9:.2f}B" if v is not None else "N/A"

            def fmt_x(v):
                return f"{v:.2f}x" if v is not None else "N/A"

            with d1:
                st.markdown("**Cash Flow Statement**")
                st.markdown(f"- Operating Cash Flow: **{fmt_b(data.get('operating_cash_flow'))}**")
                st.markdown(f"- Capital Expenditure: **{fmt_b(data.get('capex'))}**")
                st.markdown(f"- FCF₀ (Base Free Cash Flow): **{fmt_b(data['fcf'])}**")

            with d2:
                st.markdown("**Balance Sheet**")
                st.markdown(f"- Total Debt: **{fmt_b(data['total_debt'])}**")
                st.markdown(f"- Cash & Equivalents: **{fmt_b(data['cash'])}**")
                st.markdown(f"- Net Debt: **{fmt_b(data['net_debt'])}**")
                st.markdown(f"- Shares Outstanding: **{data['shares_outstanding'] / 1e9:.2f}B**")

            with d3:
                st.markdown("**Market Data**")
                st.markdown(f"- Current Price: **${data['current_price']:,.2f}**")
                st.markdown(f"- Market Cap: **{fmt_b(data.get('market_cap'))}**")
                st.markdown(f"- Revenue: **{fmt_b(data.get('revenue'))}**")
                st.markdown(f"- EBITDA: **{fmt_b(data.get('ebitda'))}**")
                st.markdown(f"- P/E Ratio: **{fmt_x(data.get('pe_ratio'))}**")

        # ── Formula & Assumptions ─────────────────────────────────────────────
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

        # ── Key metrics ───────────────────────────────────────────────────────
        col1, col2, col3 = st.columns(3)
        col1.metric("Intrinsic Value", f"${intrinsic:,.2f}")
        col2.metric("Current Price", f"${market:,.2f}")

        if margin >= 0:
            col3.metric("Margin of Safety", f"+{margin:.1f}%", delta="Undervalued")
        else:
            col3.metric("Margin of Safety", f"{margin:.1f}%", delta="Overvalued", delta_color="inverse")

        st.divider()

        # ── Chart: PV of FCFs vs Terminal Value ───────────────────────────────
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

        # ── Year-by-year table ────────────────────────────────────────────────
        with col_table:
            st.subheader("Year-by-Year FCF Breakdown")
            df = pd.DataFrame(result["rows"])
            df["Projected FCF ($B)"] = df["Projected FCF ($B)"].map("{:.2f}".format)
            df["Discount Factor (1+r)^t"] = df["Discount Factor"].map("{:.3f}".format)
            df["PV of FCF ($B)"] = df["PV of FCF ($B)"].map("{:.2f}".format)
            df = df.drop(columns=["Discount Factor"])
            st.dataframe(df, hide_index=True, use_container_width=True)

        # ── Summary table ─────────────────────────────────────────────────────
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

else:
    st.info("Enter a ticker and adjust parameters in the sidebar, then click **Calculate Intrinsic Value**.")
