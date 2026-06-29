"""
WRS Portfolio Dashboard — Streamlit wrapper.

Loads and embeds the SAME `portfolio_dashboard.html` you open locally, so the
Streamlit version is identical to the local tool. On top of that it fetches live
market + news data server-side (keys stay hidden in st.secrets) and:

  1) injects the fresh data into the embedded page, and
  2) writes a `market_snapshot.js` snapshot next to the HTML so the LOCAL file
     (opened by double-clicking) shows the last fetched data too.

No keys configured? Everything still runs — the dashboard just shows placeholders.

Run:   streamlit run streamlit_portfolio.py
"""
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import market_data

st.set_page_config(page_title="WRS Portfolio Dashboard", layout="wide",
                   initial_sidebar_state="collapsed")

# Strip Streamlit chrome so the embedded dashboard fills the window edge-to-edge.
st.markdown("""
<style>
  #MainMenu, footer, header {visibility:hidden;}
  .block-container {padding:0 !important; max-width:100% !important;}
  [data-testid="stSidebar"] {display:none;}
  iframe {border:0;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner=False)   # refresh at most every 15 minutes
def fetch_market():
    return market_data.get_market_data()


try:
    market = fetch_market()
except Exception:
    market = {}

here = Path(__file__).parent
html = (here / "portfolio_dashboard.html").read_text(encoding="utf-8")

payload = json.dumps(market)

# 1) Snapshot file so the local (file://) copy can read the same data.
try:
    (here / "market_snapshot.js").write_text(f"window.WRS_MARKET = {payload};", encoding="utf-8")
except Exception:
    pass

# 2) Inject fresh data into the embedded page (overrides the file snapshot).
html = html.replace("<!--WRS_MARKET_INJECT-->", f"<script>window.WRS_MARKET = {payload};</script>")

components.html(html, height=1600, scrolling=True)
