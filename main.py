"""
DCF Stock Valuation App

Run with:
    uv run streamlit run main.py
"""

import streamlit as st

from ui.sidebar import render_sidebar
from ui.simple_dcf_tab import render_simple_dcf_tab
from ui.damodaran_dcf_tab import render_damodaran_dcf_tab
from ui.reverse_dcf_tab import render_reverse_dcf_tab

st.set_page_config(page_title="DCF Valuation", page_icon="📈", layout="wide")

st.title("📈 DCF Stock Valuation")
st.caption("Discounted Cash Flow model powered by Yahoo Finance data")

render_sidebar()

tab_dcf, tab_damodaran, tab_reverse = st.tabs(["📈 Simple DCF", "🏗️ Damodaran DCF", "🔄 Reverse DCF"])

with tab_dcf:
    render_simple_dcf_tab()

with tab_damodaran:
    render_damodaran_dcf_tab()

with tab_reverse:
    render_reverse_dcf_tab()
