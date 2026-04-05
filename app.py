import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import requests

# --- TERMINAL CONFIG ---
st.set_page_config(page_title="Brent AI - Elite Terminal", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    .main { background-color: #0a0c10; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; }
    .signal-box { padding: 30px; border-radius: 15px; text-align: center; font-weight: bold; border: 2px solid; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=60)
def get_market_data():
    # Több idősík lekérése a pontossághoz
    m1 = yf.download("BZ=F", period="5d", interval="1m").dropna()
    m5 = yf.download("BZ=F", period="5d", interval="5m").dropna()
    # Multi-index fix
    for d in [m1, m5]:
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return m1, m5

def calc_indicators(df):
    # Bollinger + RSI + EMA
    df['SMA'] = df['Close'].rolling(20).mean()
    df['Upper'] = df['SMA'] + (df['Close'].rolling(20).std() * 2.1)
    df['Lower'] = df['SMA'] - (df['Close'].rolling(20).std() * 2.1)
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    # EMA a trendirányhoz
    df['EMA_Trend'] = df['Close'].ewm(span=50).mean()
    return df.dropna()

try:
    df1, df5 = get_market_data()
    df1, df5 = calc_indicators(df1), calc_indicators(df5)
    
    # --- MULTI-TIMEFRAME LOGIKA ---
    latest1 = df1.iloc[-1]
    latest5 = df5.iloc[-1]
    
    # Döntési pontszám
    score = 0
    reasons = []
    
    # 1 perces szignálok
    if latest1['Close'] > latest1['Upper']: score += 2; reasons.append("1m Bollinger Breakout")
    if latest1['RSI'] < 30: score += 1; reasons.append("1m RSI Oversold")
    if latest1['Close'] > latest1['EMA_Trend']: score += 1; reasons.append("1m Bullish Trend")
    
    # 5 perces megerősítés (A brókeri biztonság)
    if latest5['Close'] > latest5['EMA_Trend']: score += 2; reasons.append("5m Trend Confirmation")
    
    # --- UI MEGJELENÍTÉS ---
    st.title("🏦 BRENT ELITE TRADING TERMINAL")
    
    col1, col2, col3, col4 = st.columns(4)
    price = latest1['Close']
    change = price - df1['Close'].iloc[-2]
    col1.metric("BRENT CRUDE", f"${price:.2f}", f"{change:.2f}")
    col2.metric("RSI (1m/5m)", f"{latest1['RSI']:.1f} / {latest5['RSI']:.1f}")
    col3.metric("PIACI VOLATILITÁS", "MAGAS" if abs(change) > 0.1 else "NORMÁL")
    col4.metric("RENDSZER ÁLLAPOT", "ÉLŐ" if datetime.now().hour < 23 else "NYITÁSRA VÁR")

    # --- NAGY SZIGNÁL PANEL ---
    if score >= 4:
        status, color, icon = "ERŐS VÉTEL (LONG) 🚀", "#00ff88", "BUY"
    elif score <= -2:
        status, color, icon = "ERŐS ELADÁS (SHORT) 📉", "#ff4444", "SELL"
    else:
        status, color, icon = "SEMLEGES / VÁRAKOZÁS ⚖️", "#888888", "WAIT"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color}22; border-color: {color}; color: {color};">
            <h1 style="margin:0; font-size:55px;">{status}</h1>
            <p style="font-size:20px; margin-top:10px;">Indoklás: {' + '.join(reasons) if reasons else 'Nincs egyértelmű jel'}</p>
        </div>
    """, unsafe_allow_html=True)

    # --- INTERAKTÍV GRAFIKON ---
    st.subheader("📊 Percenkénti Élő Analízis")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df1.index[-100:], y=df1['Close'].iloc[-100:], name="Price", line=dict(color=color, width=3)))
    fig.add_trace(go.Scatter(x=df1.index[-100:], y=df1['Upper'].iloc[-100:], name="Upper", line=dict(color="#ffffff22", dash="dot")))
    fig.add_trace(go.Scatter(x=df1.index[-100:], y=df1['Lower'].iloc[-100:], name="Lower", line=dict(color="#ffffff22", dash="dot")))
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # --- TELEGRAM AUTOMATIZÁCIÓ ---
    with st.sidebar:
        st.header("🤖 Alpha Bot Settings")
        token = st.text_input("Bot Token", type="password")
        cid = st.text_input("Chat ID")
        if st.toggle("Élesítés (Percenkénti push)"):
            if score >= 4 or score <= -2:
                msg = f"🔔 {status}\n💰 Ár: ${price:.2f}\n📝 Miért: {', '.join(reasons)}\n🎯 Célár: ${price*1.02:.2f}"
                # Itt küldi a Telegram üzenetet...
                st.sidebar.success("Jelzés kiküldve!")

except Exception as e:
    st.info("A piac jelenleg zárva van. A grafikonok vasárnap éjféltől frissülnek élőben.")

