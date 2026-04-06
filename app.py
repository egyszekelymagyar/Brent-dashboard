import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import feedparser
import time
import requests
from datetime import datetime

# =================================================================
# 1. ELITE TERMINAL DESIGN
# =================================================================
st.set_page_config(page_title="BRENT AI MULTI-TF PRO", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .metric-card { background-color: #1a1c24; padding: 15px; border-radius: 10px; border: 1px solid #30363d; text-align: center; }
    .signal-hero { padding: 30px; border-radius: 20px; text-align: center; margin: 20px 0; border: 3px solid white; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADATKEZELŐ ÉS ELEMZŐ MOTOR (MULTI-TF)
# =================================================================
@st.cache_data(ttl=60)
def get_all_data():
    # Az összes szükséges idősík letöltése
    tfs = {"1m": "1d", "5m": "5d", "1h": "1mo"}
    results = {}
    for tf, prd in tfs.items():
        df = yf.download("BZ=F", period=prd, interval=tf, progress=False)
        # Multi-index fix (Yahoo Finance új formátum)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        results[tf] = df.dropna()
    return results

def get_sentiment():
    # Élő hír-szentiment (RSS)
    feed = feedparser.parse("https://google.com")
    score = 0.5
    headlines = []
    bullish = ['rise', 'cut', 'shortage', 'demand', 'up', 'conflict', 'war']
    bearish = ['drop', 'glut', 'surplus', 'down', 'recession', 'lower']
    
    for entry in feed.entries[:5]:
        text = entry.title.lower()
        headlines.append(entry.title)
        for w in bullish: 
            if w in text: score += 0.08
        for w in bearish: 
            if w in text: score -= 0.08
    return min(max(score, 0.1), 0.9), headlines

# =================================================================
# 3. KALKULÁCIÓ ÉS LOGIKA
# =================================================================
data = get_all_data()
sent_score, news = get_sentiment()

# Elemzés idősíkonként
tf_scores = []
for tf in ["1m", "5m", "1h"]:
    df = data[tf]
    df['SMA20'] = df['Close'].rolling(20).mean()
    # RSI számítás
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    last = df.iloc[-1]
    # Pontozás: Ár vs SMA (0.5 pont) + RSI (0.5 pont)
    score = 0
    if last['Close'] > last['SMA20']: score += 0.5
    if last['RSI'] < 40: score += 0.5  # Vételi lehetőség
    if last['RSI'] > 60: score -= 0.5  # Eladási nyomás
    tf_scores.append(score)

# FÚZIÓ: 40% Technikai (Multi-TF átlag) + 60% Szentiment
tech_avg = sum(tf_scores) / 3
# Skálázás 0-100 közé (egyszerűsített modell)
final_score = (sent_score * 60) + (tech_avg * 40) + 20 
final_score = min(max(final_score, 5), 95)

# =================================================================
# 4. DASHBOARD MEGJELENÍTÉS
# =================================================================
st.title("🏦 BRENT AI - MULTI-TIMEFRAME TERMINAL")

# Felső metrikák
m1, m2, m3, m4 = st.columns(4)
curr_price = data["1m"].iloc[-1]['Close']
m1.metric("AKTUÁLIS ÁR", f"${curr_price:.2f}")
m2.metric("SZENTIMENT", f"{sent_score:.2f}")
m3.metric("RSI (5m)", f"{data['5m'].iloc[-1]['RSI']:.1f}")
m4.metric("TREND (1h)", "UP 🟢" if tf_scores[2] > 0 else "DOWN 🔴")

# SZIGNÁL PANEL
if final_score > 70: 
    status, color = "ERŐS VÉTEL! 🚀", "#2ecc71"
elif final_score < 30: 
    status, color = "ERŐS ELADÁS! 📉", "#e74c3c"
else: 
    status, color = "VÁRAKOZÁS ⚖️", "#34495e"

st.markdown(f"""<div class="signal-hero" style="background-color: {color};">
    <h1 style="color: white; font-size: 50px; margin: 0;">{status}</h1>
    <h2 style="color: white; opacity: 0.9;">Összetett Bizalmi Index: {final_score:.1f}%</h2>
</div>""", unsafe_allow_html=True)

# Grafikon és Hírek
col_left, col_right = st.columns([2, 1])

with col_left:
    fig = go.Figure()
    df_p = data["5m"].tail(100)
    fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name="Brent 5m"))
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("📰 Piaci Hírek")
    for n in news:
        st.info(n)

# Vezérlő pult a sidebaron
with st.sidebar:
    st.header("⚙️ Beállítások")
    refresh = st.toggle("Automata frissítés (30s)", value=True)
    t_token = st.text_input("Telegram Bot Token", type="password")
    t_cid = st.text_input("Chat ID")

    if refresh:
        time.sleep(30)
        st.rerun()
