"""
DCF Stock Valuation App

Run with:
    uv run streamlit run main.py
"""

import streamlit as st

import ui.sidebar as sidebar
import ui.simple_dcf_tab as simple_dcf_tab
import ui.three_phase_dcf_tab as three_phase_dcf_tab

st.set_page_config(page_title="DCF Valuation", page_icon="📈", layout="wide")

st.title("📈 DCF Stock Valuation")
st.caption("Discounted Cash Flow model powered by Yahoo Finance data")

sidebar.render_sidebar()

tab_simple_dcf, tab_three_phase = st.tabs([
    "📈 Simple DCF",  "🔬 Three-Phase DCF",
])

with tab_three_phase:
    three_phase_dcf_tab.render_three_phase_dcf_tab()

with tab_simple_dcf:
    simple_dcf_tab.render_simple_dcf_tab()