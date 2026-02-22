import streamlit as st

import datasource.fetcher as fetcher
import ui.utils as utils


def render_sidebar():
    with st.sidebar:
        st.header("Stock Lookup")

        ticker = st.text_input("Ticker Symbol", value="AAPL").upper().strip()

        if st.button("Load Stock Data", type="primary", use_container_width=True):
            if not ticker:
                st.error("Please enter a ticker symbol.")
            else:
                with st.spinner(f"Fetching data for {ticker}..."):
                    try:
                        st.session_state.stock_data = fetcher.fetch_stock_data(ticker)
                        st.session_state.stock_ticker = ticker
                    except ValueError as e:
                        st.error(str(e))

        if "stock_data" not in st.session_state:
            return

        data = st.session_state.stock_data
        loaded_ticker = st.session_state.stock_ticker

        if ticker != loaded_ticker:
            st.caption(f"⚠ Showing data for {loaded_ticker}. Click Load to refresh.")

        st.divider()

        st.markdown(f"**{data['company_name']}** ({loaded_ticker})")
        if data.get("sector") or data.get("industry"):
            st.caption(f"{data.get('sector', '')}  ·  {data.get('industry', '')}")

        st.divider()

        st.markdown("**Income Statement**")
        st.markdown(f"- EBIT: **{utils.fmt_b(data.get('ebit'))}**")
        tax_str = f"{data['effective_tax_rate'] * 100:.1f}%" if data.get('effective_tax_rate') else "N/A"
        st.markdown(f"- Eff. Tax Rate: **{tax_str}**")
        st.markdown(f"- NOPAT: **{utils.fmt_b(data.get('nopat'))}**")

        st.markdown("**Cash Flow Statement**")
        st.markdown(f"- Op CF: **{utils.fmt_b(data.get('operating_cash_flow'))}**")
        st.markdown(f"- CapEx: **{utils.fmt_b(data.get('capex'))}**")
        st.markdown(f"- FCF₀: **{utils.fmt_b(data['fcf'])}**")

        st.markdown("**Balance Sheet**")
        st.markdown(f"- Total Debt: **{utils.fmt_b(data['total_debt'])}**")
        st.markdown(f"- Cash: **{utils.fmt_b(data['cash'])}**")
        st.markdown(f"- Net Debt: **{utils.fmt_b(data['net_debt'])}**")
        st.markdown(f"- Shares: **{data['shares_outstanding'] / 1e9:.2f}B**")

        st.markdown("**Market Data**")
        st.markdown(f"- Price: **${data['current_price']:,.2f}**")
        st.markdown(f"- Mkt Cap: **{utils.fmt_b(data.get('market_cap'))}**")
        st.markdown(f"- Revenue: **{utils.fmt_b(data.get('revenue'))}**")
        st.markdown(f"- EBITDA: **{utils.fmt_b(data.get('ebitda'))}**")
        st.markdown(f"- P/E: **{utils.fmt_x(data.get('pe_ratio'))}**")
