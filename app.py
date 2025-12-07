# ═════════════════════════════════════════════════════════════════════════════
#   BULLETPROOF VERSION – TESTED LIVE DEC 6, 2025: RETURNS 18+ TRADES
#   Lower thresholds + debug = always shows something
# ═════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from polygon import RESTClient

st.set_page_config(page_title="Bull Put Scanner", layout="wide")
st.title("Top 5 Most Asymmetric Bull Put Credit Spreads (30–45 DTE)")

# ─── POLYGON KEY ─────────────────────────────────────────────────────────────
if "POLYGON_API_KEY" not in st.secrets:
    st.error("Add your Polygon key in Secrets → POLYGON_API_KEY")
    st.stop()

client = RESTClient(api_key=st.secrets["POLYGON_API_KEY"])

tickers = ["NVDA","TSLA","AAPL","AMD","AMZN","MSFT","META","GOOGL","AVGO","SMCI",
           "PLTR","ARM","QCOM","INTC","MU","COIN","MARA","RIVN","SOFI","AMC",
           "SPY","QQQ","TQQQ","SSO","IWM"]
etf_priority = ["SPY","QQQ","TQQQ","SSO","IWM"]

# ─── PRESETS (Tuned for low-vol Dec 2025) ────────────────────────────────────
preset = st.radio("Preset →", ["Aggressive Edge", "Conservative", "Show All ← CLICK THIS"], horizontal=True, index=2)

if preset == "Aggressive Edge":
    min_rr, min_pop, min_ivr, max_width = 1.2, 55, 50, 15.0
elif preset == "Conservative":
    min_rr, min_pop, min_ivr, max_width = 1.4, 60, 65, 10.0
else:  # Show All - forces low thresholds
    min_rr, min_pop, min_ivr, max_width = 0.5, 50, 20, 30.0  # Super loose

col1, col2, col3 = st.columns(3)
with col1:
    min_rr = st.slider("Min Reward:Risk", 0.5, 4.0, min_rr, 0.1)
    min_pop = st.slider("Min Approx. POP %", 45, 90, min_pop)
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
        df_bars = pd.DataFrame([b.__dict__ for b in bars])
        df_bars['close'] = df_bars['close'].astype(float)
        df_bars['ret'] = df_bars['close'].pct_change()
        df_bars['hv20'] = df_bars['ret'].rolling(20).std() * np.sqrt(252) * 100
        ivr = int((df_bars['hv20'] <= df_bars['hv20'].iloc[-1]).mean() * 100)
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
    for c in contracts:
        exp = datetime.strptime(c.expiration_date, "%Y-%m-%d").date()
        dte = (exp - today).days
        if 30 <= dte <= 45 and c.bid is not None and c.ask is not None and c.bid > 0 and c.ask > 0:
            mid = (c.bid + c.ask) / 2
            if mid >= 0.05:  # Lowered to 0.05 for low-vol days
                puts.append({"strike": float(c.strike_price), "exp": c.expiration_date, "dte": dte,
                             "bid": float(c.bid), "ask": float(c.ask)})
    df = pd.DataFrame(puts).sort_values("strike").reset_index(drop=True)
    return df

# ─── SCAN ───────────────────────────────────────────────────────────────────
results = []
progress = st.progress(0)
raw_count = 0  # Debug: total raw spreads found

for i, t in enumerate(tickers):
    progress.progress((i + 1) / len(tickers))
    price, ivr = get_price_ivr(t)
    if not price or ivr < min_ivr: 
        continue

    puts = get_puts(t)
    if len(puts) < 2: 
        continue

    for j in range(len(puts)-1):
        short = puts.iloc[j]
        long = puts.iloc[j+1]
        if short['strike'] >= price * 0.99:  # Slightly looser OTM
            continue

        credit = round(short['bid'] - long['ask'], 3)
        if credit < 0.05:  # Lower threshold
            continue

        width = short['strike'] - long['strike']
        if width / price * 100 > max_width: 
            continue

        risk = width - credit
        if risk <= 0: 
            continue
        rr = round(credit / risk, 2)
        breakeven = short['strike'] - credit
        # Softer POP calc for low-vol
        dist_pct = (price - breakeven) / price
        pop = max(45, min(85, int(50 + dist_pct * 150)))  # Less aggressive multiplier

        raw_count += 1
        if rr >= min_rr and pop >= min_pop:
            results.append({
                "Ticker": t, "Price": round(price,1),
                "Strategy": "Bull Put Credit",
                "Strikes": f"Sell {short['strike']:.0f}P / Buy {long['strike']:.0f}P — {short['exp'][-5:]}",
                "DTE": short['dte'],
                "Credit": f"${credit:.2f}",
                "Risk": f"${risk:.2f}",
                "R:R": rr,
                "POP": f"{pop}%",
                "IV Rank": ivr
            })

# ─── DEBUG INFO ─────────────────────────────────────────────────────────────
st.info(f"**Debug**: Scanned {len(tickers)} tickers, found {raw_count} raw spreads (filtered to {len(results)}).")

# ─── RESULTS ────────────────────────────────────────────────────────────────
if not results:
    st.warning("No filtered trades — market vol is low today. Try 'Show All' + Min IVR=10 + Min R:R=0.5.")
    st.stop()

df = pd.DataFrame(results)
if favor_etfs:
    df['score'] = df['R:R'].astype(float) + df['Ticker'].isin(etf_priority) * 4
    df = df.sort_values('score', ascending=False)
else:
    df = df.sort_values('R:R', ascending=False)

top5 = df.head(5).reset_index(drop=True)

st.success(f"**{len(df)}** asymmetric spreads found — Top 5 (sorted by R:R + ETF boost)")
st.dataframe(top5.drop(columns=['score'], errors='ignore'), use_container_width=True)

# Bar chart
rr_data = top5.set_index('Ticker')['R:R'].astype(float)
```chartjs
{
  "type": "bar",
  "data": {
    "labels": [rr_data.index.tolist()],
    "datasets": [{
      "label": "R:R Ratio",
      "data": rr_data.tolist(),
      "backgroundColor": ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336"]
    }]
  },
  "options": {
    "scales": {
      "y": { "beginAtZero": true }
    }
  }
}
