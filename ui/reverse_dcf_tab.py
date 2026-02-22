import pandas as pd
import streamlit as st

import apps.reverse_dcf_app as reverse_dcf_app
import datasource.fetcher as fetcher
import ui.utils as utils


def render_reverse_dcf_tab():
    st.caption("Given the current market price, what near-term growth rate is the market pricing in?")

    tc, bc = st.columns([3, 1])
    with tc:
        ticker = st.text_input("Ticker Symbol", value="AAPL", key="rdcf_ticker_input").upper().strip()
    with bc:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        load = st.button("Load", type="primary", key="rdcf_load", use_container_width=True)

    if load and ticker:
        with st.spinner(f"Fetching {ticker}..."):
            try:
                st.session_state.rdcf_stock_data = fetcher.fetch_stock_data(ticker)
                st.session_state.rdcf_stock_ticker = ticker
            except ValueError as e:
                st.error(str(e))
                return

    if "rdcf_stock_data" not in st.session_state:
        st.info("Enter a ticker and click Load.")
        return

    rdata = st.session_state.rdcf_stock_data
    loaded_ticker = st.session_state.rdcf_stock_ticker

    # ── Inputs ────────────────────────────────────────────────────────────────
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        rdcf_years = st.slider("n — Near-term Forecast Years", 3, 10, 5, key="rdcf_years")
    with rc2:
        rdcf_terminal_growth = st.slider(
            "g∞ — Terminal Growth Rate (%)", 1.0, 4.0, 2.5, key="rdcf_g_inf"
        ) / 100
    with rc3:
        rdcf_wacc = st.slider(
            "r — Discount Rate / WACC (%)", 6.0, 15.0, 10.0, key="rdcf_wacc"
        ) / 100

    if not st.button("Solve for Implied Growth Rate", type="primary", key="rdcf_calc"):
        return

    if rdata.fcf <= 0:
        st.warning(
            f"FCF₀ is negative (${rdata.fcf / 1e9:.2f}B). "
            "Reverse DCF may not converge for companies with negative free cash flow."
        )

    try:
        implied_g = reverse_dcf_app.solve_implied_g(
            fcf=rdata.fcf,
            wacc=rdcf_wacc,
            terminal_growth=rdcf_terminal_growth,
            net_debt=rdata.net_debt,
            shares_outstanding=rdata.shares_outstanding,
            years=rdcf_years,
            current_price=rdata.current_price,
        )
    except Exception as e:
        st.error(f"Reverse DCF calculation failed: {e}")
        return

    market = rdata.current_price

    st.subheader(f"{rdata.company_name} ({loaded_ticker})")
    if rdata.sector or rdata.industry:
        st.caption(f"{rdata.sector or ''}  ·  {rdata.industry or ''}")

    # ── Result metrics ────────────────────────────────────────────────────────
    m1, m2 = st.columns(2)
    m1.metric(
        "Implied Near-term Growth Rate (g)",
        f"{implied_g * 100:.2f}%" if implied_g is not None else "N/A",
        help="Near-term FCF growth rate that makes the DCF intrinsic value equal the current market price",
    )
    m2.metric("Current Market Price", f"${market:,.2f}")

    if implied_g is None:
        st.warning(
            "Could not solve for implied g. The current price may be outside the range "
            "achievable by any growth rate in [-50%, 100%] at the given inputs."
        )
    else:
        st.info(
            f"To justify **${market:,.2f}**, the market is pricing in FCF₀ growing at "
            f"**{implied_g * 100:.1f}%/yr** for {rdcf_years} years "
            f"(r = {rdcf_wacc * 100:.1f}%, g∞ = {rdcf_terminal_growth * 100:.1f}%)."
        )

    st.divider()

    # ── Formula & Assumptions expander ────────────────────────────────────────
    with st.expander("📐 Formula & Assumptions", expanded=False):
        fcol, acol = st.columns([3, 2])

        with fcol:
            st.markdown("**Reverse DCF — Solving for Implied g**")
            st.latex(r"""
                P_{\text{market}} = \sum_{t=1}^{n} \frac{FCF_0 \cdot (1+g_t)}{(1+r)^t}
                    + \frac{TV(g)}{(1+r)^n}
                    - \frac{\text{Net Debt}}{\text{Shares}}
            """)
            st.markdown(
                "Numerically solves for $g$ (year-1 rate, declining linearly to $g_\\infty$) "
                "such that the DCF formula equals the market price. "
                "Uses `scipy.optimize.brentq` over $g \\in [-50\\%, 100\\%]$."
            )

        with acol:
            st.markdown("**Inputs**")
            for label, value in [
                ("FCF₀",                 utils.fmt_b(rdata.fcf)),
                ("r — Discount Rate",    f"{rdcf_wacc * 100:.1f}%"),
                ("g∞ — Terminal Growth", f"{rdcf_terminal_growth * 100:.1f}%"),
                ("n — Forecast Years",   str(rdcf_years)),
                ("Net Debt",             utils.fmt_b(rdata.net_debt)),
                ("Shares Outstanding",   f"{rdata.shares_outstanding / 1e9:.2f}B"),
                ("Market Price",         f"${market:,.2f}"),
            ]:
                st.markdown(f"- {label}: **{value}**")

    # ── Sensitivity table ──────────────────────────────────────────────────────
    st.subheader("Sensitivity: Implied g across discount rates")
    st.caption("How implied g changes as r varies ±2% in 0.5% steps (g∞ and n held fixed)")

    r_deltas = [-0.020, -0.015, -0.010, -0.005, 0.000, 0.005, 0.010, 0.015, 0.020]
    sens_rows = []
    for delta in r_deltas:
        r_test = rdcf_wacc + delta
        if r_test <= rdcf_terminal_growth:
            sens_rows.append({"r (WACC)": f"{r_test * 100:.1f}%", "Implied g": "N/A (r ≤ g∞)"})
            continue
        try:
            g_val = reverse_dcf_app.solve_implied_g(
                fcf=rdata.fcf,
                wacc=r_test,
                terminal_growth=rdcf_terminal_growth,
                net_debt=rdata.net_debt,
                shares_outstanding=rdata.shares_outstanding,
                years=rdcf_years,
                current_price=market,
            )
            label = f"{g_val * 100:.2f}%" if g_val is not None else "N/A"
            if delta == 0.0:
                label += "  ← selected r"
        except Exception:
            label = "error"
        sens_rows.append({"r (WACC)": f"{r_test * 100:.1f}%", "Implied g": label})

    st.dataframe(pd.DataFrame(sens_rows), hide_index=True, use_container_width=True)
