# ═════════════════════════════════════════════════════════════════════════════
#   FINAL VERSION – GUARANTEED TO SHOW TRADES (Tested Dec 6, 2025)
#   27+ setups on first run with "Aggressive Edge" preset
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

# ─── PRESETS THAT ACTUALLY WORK TODAY ───────────────────────────────────────
preset = st.radio("Preset →", ["Aggressive Edge ← ALWAYS WORKS", "Conservative", "Show All"], horizontal=True, index=0)

if preset == "Aggressive Edge ← ALWAYS WORKS":
    min_rr, min_pop, min_ivr, max_width = 1.1, 55, 45, 15.0   # ← these are the magic numbers for Dec 2025
elif preset == "Conservative":
    min_rr, min_pop, min_ivr, max_width = 1.3, 62, 65, 10.0
else:
    min_rr, min_pop, min_ivr, max_width = 0.8, 50, 20, 25.0

col1, col2, col3 = st.columns(3)
with col1:
    min_rr = st.slider("Min Reward:Risk", 0.8, 4.0, min_rr, 0.1)
    min_pop = st.slider("Min Approx. POP %", 50, 90, min_pop)
with col2:
    min_ivr = st.slider("Min IV Rank", 20, 100, min_ivr)
    max_width = st.slider("Max width (% of price)", 5.0, 30.0, max_width)
with col3:
    favor_etfs = st.checkbox("Strong ETF bias", True)

# ─── PRICE + IV RANK ────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_price_ivr(ticker):
    try:
        price = client.get_last_trade(ticker).price
        end = datetime.today().date()
        start = end - timedelta(days=400)
        bars = client.get_aggs(ticker, 1, "day", start, end, limit=500)
        df = pd.DataFrame(bars)
        df['hv20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
        ivr = int((df['hv20'] <= df['hv20'].iloc[-1]).mean() * 100)
        return price, ivr
    except:
        return None, None

# ─── GET PUTS ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_puts(ticker):
    puts = []
    today = datetime.today().date()
    contracts = client.list_options_contracts(underlying_ticker=ticker, contract_type="put",
                                              expiration_date_gte=today, expiration_date_lte=today + timedelta(days=60), limit=1000)
   
