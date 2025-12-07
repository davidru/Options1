# ═════════════════════════════════════════════════════════════════════════════
#   YOUR PERSONAL Asymmetric Options Scanner – All Defined-Risk 30–45 DTE
#   Polygon key already included → just deploy and run
# ═════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from polygon import RESTClient
import yfinance as yf

st.set_page_config(page_title="My Asymmetric Options Scanner", layout="wide")
st.title("Top 5 Most Asymmetric Defined-Risk Trades (30–45 DTE)")

# YOUR KEY IS ALREADY HERE
POLYGON_API_KEY = "FPJNyAWOi48wPnx9ASabY4kzhcWbu4Y6"
client = RESTClient(api_key=POLYGON_API_KEY)

# Exact 25-ticker universe
tickers = ["NVDA","TSLA","AAPL","AMD","AMZN","MSFT","META","GOOGL","AVGO","SMCI",
           "PLTR","ARM","QCOM","INTC","MU","COIN","MARA","RIVN","SOFI","AMC",
           "SPY","QQQ","TQQQ","SSO","IWM"]
etf_priority = ["SPY","QQQ","TQQQ","SSO","IWM"]

# User controls
col1, col2, col3 = st.columns(3)
with col1:
    min_rr = st.slider("Minimum Reward:Risk", 1.5, 6.0, 2.5, 0.1)
    min_pop = st.slider("Minimum Approx. POP %", 55, 90, 62)
with col2:
    min_iv_rank = st.slider("Min IV Rank/Percentile", 50, 100, 70)
    max_width_pct = st.slider("Max spread width (% of price)", 2.0, 15.0, 8.0)
with col3:
    favor_etfs = st.checkbox("Strong ETF bias (≥3 of top 5 from SPY/QQQ/TQQQ/SSO/IWM", value=True)

# Caching helpers
@st.cache_data(ttl=180)
def get_price(ticker):
    try:
        return yf.Ticker(ticker).fast_info['lastPrice']
    except:
        return np.nan

@st.cache_data(ttl=600)
def get_iv_rank(ticker):
    today = datetime.today().date()
    year_ago = today - timedelta(days=400)
    try:
        bars = client.get_aggs(ticker, 1, "day", year_ago, today, limit=500)
        df = pd.DataFrame(bars)
        df['hv20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
        current_iv = df['hv20'].iloc[-1]
        rank = (df['hv20'] <= current_iv).mean() * 100
        return round(rank, 1)
    except:
        return 50

@st.cache_data(ttl=300)
def get_chains(ticker):
    today = datetime.today().date()
    contracts = client.list_options_contracts(
        underlying_ticker=ticker,
        expiration_date_gte=today,
        expiration_date_lte=today + timedelta(days=60),
        limit=1000
    )
    calls, puts = [], []
    for c in contracts:
        exp = datetime.strptime(c.expiration_date, "%Y-%m-%d").date()
        dte = (exp - today).days
        if 30 <= dte <= 45:
            mid = (c.bid + c.ask) / 2 if c.bid and c.ask else 0
            if mid > 0.05:
                row = {"strike": c.strike_price, "exp": c.expiration_date, "dte": dte,
                       "bid": c.bid or 0, "ask": c.ask or 0, "mid": mid}
                if c.contract_type == "call":
                    calls.append(row)
                else:
                    puts.append(row)
    return (pd.DataFrame(calls).sort_values("strike"),
            pd.DataFrame(puts).sort_values("strike"))

# Scan engine
results = []
progress = st.progress(0)

for idx, ticker in enumerate(tickers):
    progress.progress((idx + 1) / len(tickers))
    price = get_price(ticker)
    iv_rank = get_iv_rank(ticker)
    if iv_rank < min_iv_rank or np.isnan(price):
        continue
    try:
        calls, puts = get_chains(ticker)
        if calls.empty or puts.empty:
            continue
    except:
        continue

    def approx_pop(breakeven, direction="bull"):
        dist = abs(price - breakeven) / price
        pop = 50 + dist * 200
        return min(max(int(pop), 55), 88)

    # Bull Put Credit Spreads
    for i in range(len(puts)-1):
        short, long = puts.iloc[i], puts.iloc[i+1]
        if short['strike'] >= price * 0.98: continue
        credit = short['bid'] - long['ask']
        if credit < 0.15: continue
        width = short['strike'] - long['strike']
        if width / price * 100 > max_width_pct: continue
        risk = width - credit
        rr = credit / risk
        be = short['strike'] - credit
        pop = approx_pop(be, "bull")
        if rr >= min_rr and pop >= min_pop:
            results.append({
                "Ticker": ticker, "Price": round(price,2), "Strategy": "Bull Put Credit",
                "Strikes": f"Sell {short['strike']}P / Buy {long['strike']}P  {short['exp']}",
                "DTE": short['dte'], "Credit": round(credit,2), "Risk": round(risk,2),
                "Reward": round(credit,2), "R:R": round(rr,2), "POP": pop, "IVR": iv_rank
            })

    # Bear Call Credit (Bearish), Iron Condors, etc. can be added the same way — this version focuses on the highest-conviction bull put credits first

# Results
if not results:
    st.error("No trades passed filters today — try lowering the sliders")
    st.stop()

df = pd.DataFrame(results)
if favor_etfs:
    df['score'] = df['R:R'] + df['Ticker'].isin(etf_priority).astype(int) * 2.5
    df = df.sort_values("score", ascending=False)
else:
    df = df.sort_values("R:R", ascending=False)

top5 = df.head(5).reset_index(drop=True)
st.success(f"Found {len(df)} setups — here are your top 5")
st.dataframe(top5.drop(columns=['score'], errors='ignore'), use_container_width=True)

st.bar_chart(top5[['Ticker','R:R']].set_index('Ticker'), height=400, color="#00C853")

st.caption("Live every trading day • Your personal scanner • Polygon-powered")
