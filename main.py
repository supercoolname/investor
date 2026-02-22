"""
DCF Stock Valuation App

Run with:
    uv run streamlit run main.py
"""

import streamlit as st

from ui.sidebar import render_sidebar
from ui.simple_dcf_tab import render_simple_dcf_tab
from ui.three_phase_dcf_tab import render_three_phase_dcf_tab

st.set_page_config(page_title="DCF Valuation", page_icon="📈", layout="wide")

st.title("📈 DCF Stock Valuation")
st.caption("Discounted Cash Flow model powered by Yahoo Finance data")

render_sidebar()

tab_simple_dcf, tab_three_phase = st.tabs([
    "📈 Simple DCF",  "🔬 Three-Phase DCF",
])

with tab_three_phase:
    render_three_phase_dcf_tab()

with tab_simple_dcf:
    render_simple_dcf_tab()