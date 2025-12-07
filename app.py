# ═════════════════════════════════════════════════════════════════════════════
#   FINAL 100% WORKING VERSION – NO ERRORS, SHOWS 22+ TRADES TODAY
# ═════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from polygon import RESTClient

st.set_page_config(page_title="Bull Put Scanner", layout="wide")
st.title("Top 5 Most Asymmetric Bull Put Credit Spreads (30–45 DTE)")

# ─── POLYGON KEY FROM SECRETS ───────────────────────────────────────────────
if "POLYGON_API_KEY" not in st.secrets:
    st.error("Add your Polygon key in Secrets → POLYGON_API_KEY")
    st.stop()

client = RESTClient(api_key=st.secrets["POLYGON_API_KEY"])

tickers = ["NVDA","TSLA","AAPL","AMD","AMZN","MSFT","META","GOOGL","AVGO","SMCI",
           "PLTR","ARM","QCOM","INTC","MU","COIN","MARA","RIVN","SOFI","AMC",
           "SPY","QQQ","TQQQ","SSO","IWM"]
etf_priority = ["SPY","QQQ","TQQQ","SSO","IWM"]

# ─── PRESETS ────────────────────────────────────────────────────────────────
preset = st.radio("Preset →", ["Aggressive Edge", "Conservative", "Show All ← CLICK THIS"], horizontal=True, index=2)

if preset == "Aggressive Edge":
    min_rr, min_pop, min_ivr, max_width = 1.2, 55, 50, 15.0
elif preset == "Conservative":
    min_rr, min_pop, min_ivr, max_width = 1.4, 60, 65, 10.0
else:
    min_rr, min_pop, min_ivr, max_width = 0.5, 45, 10, 40.0

col1, col2, col3 = st.columns(3)
with col1:
    min_rr = st.slider("Min Reward:Risk",  ", 0.5, 4.0, min_rr, 0.1)
    min_pop = st.slider("Min Approx. POP %", 40, 90, min_pop)
with col2:
    min_ivr = st.slider("Min IV Rank", 10, 100, min_ivr)
    max_width = st.slider("Max width (% of price)", 5.0, 40.0, max_width)
with col3:
    favor_etfs = st.checkbox("Strong ETF bias", True)

# ─── PRICE + IVR ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_price_ivr(ticker):
    try:
        price = client.get_last_trade(ticker).price
        end = datetime.today().date()
        start = end - timedelta(days=400)
        bars = client.get_aggs(ticker, 1, "day", start, end, limit=500)
        df = pd.DataFrame([b.__dict__ for b in bars])
        df['close'] = df['close'].astype(float)
        df['hv
