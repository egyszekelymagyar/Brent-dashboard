import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import requests

# --- HIGH-CONTRAST TERMINAL CONFIG ---
st.set_page_config(page_title="Brent AI - High Contrast", layout="wide", page_icon="🏦")

# JAVÍTOTT CSS: Világos szöveg, neon keretek, olvasható metrikák
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    /* Metrika kártyák javítása */
    div[data-testid="stMetric"] {
        background-color: #1a1c24;
        border: 2px solid #30363d;
        padding: 20px;
        border-radius: 12px;
    }
    div[data-testid="stMetricLabel"] { color: #ffffff !important; font-size: 18px !important; }
    div[data-testid="stMetricValue"] { color: #00ffcc !important; font-size: 32px !important; font-weight: bold !important; }
    
    /* Nagy szignál box javítása */
    .signal-box {
        padding: 40px;
        border-radius: 20px;
        text-align: center;
        font-weight: bold;
        border: 4px solid;
        margin-bottom: 25px;
    }
    .signal-title { font-size: 55px; margin: 0; color: #ffffff; text-shadow: 2px 2px 4px #000000; }
    .signal-reason { font-size: 22px; margin-top: 15px; color: #ffffff; font-weight: normal; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=60)
def get_market_data():
    m1 = yf.download("BZ=F", period="5d", interval="1m").dropna()
    m5 = yf.download("BZ=F", period="5d", interval="5m").dropna()
    for d in [m1, m5]:
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return m1, m5

def calc_indicators(df):
    df['SMA'] = df['Close'].rolling(20).mean()
    df['Upper'] = df['SMA'] + (df['Close'].rolling(20).std() * 2.1)
    df['Lower'] = df['SMA'] - (df['Close'].rolling(20).std() * 2.1)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    df['EMA_Trend'] = df['Close'].ewm(span=50).mean()
    return df.dropna()

try:
    df1, df5 = get_market_data()
    df1, df5 = calc_indicators(df1), calc_indicators(df5)
    
    latest1 = df1.iloc[-1]
    latest5 = df5.iloc[-1]
    
    # Döntési logika
    score = 0
    reasons = []
    if latest1['Close'] > latest1['Upper']: score += 2; reasons.append("1m Bollinger Kitörés")
    if latest1['RSI'] < 30: score += 1; reasons.append("1m RSI Túladott")
    if latest1['Close'] > latest1['EMA_Trend']: score += 1; reasons.append("1m Emelkedő Trend")
    if latest5['Close'] > latest5['EMA_Trend']: score += 2; reasons.append("5m Trend Megerősítés")
    if latest1['Close'] < latest1['Lower']: score -= 2; reasons.append("1m Letörés")
    if latest1['RSI'] > 70: score -= 1; reasons.append("1m RSI Túlvett")

    # --- FEJLÉC ---
    st.title("🏦 BRENT ELITE TERMINAL")
    
    c1, c2, c3, c4 = st.columns(4)
    price = latest1['Close']
    c1.metric("BRENT ÁR", f"${price:.2f}")
    c2.metric("RSI (1m)", f"{latest1['RSI']:.1f}")
    c3.metric("5m TREND", "LONG" if latest5['Close'] > latest5['EMA_Trend'] else "SHORT")
    c4.metric("FRISSÍTÉS", datetime.now().strftime("%H:%M:%S"))

    # --- JAVÍTOTT NAGY SZIGNÁL PANEL (FEHÉR SZÖVEGGEL) ---
    if score >= 3:
        status, color = "ERŐS VÉTEL (LONG) 🚀", "#2ecc71" # Zöld
    elif score <= -2:
        status, color = "ERŐS ELADÁS (SHORT) 📉", "#e74c3c" # Piros
    else:
        status, color = "VÁRAKOZÁS ⚖️", "#95a5a6" # Szürke

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color}; border-color: #ffffff;">
            <div class="signal-title">{status}</div>
            <div class="signal-reason"><b>Indoklás:</b> {' + '.join(reasons) if reasons else 'Piaci zaj / Nincs irány'}</div>
        </div>
    """, unsafe_allow_html=True)

    # --- GRAFIKON ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df1.index[-100:], y=df1['Close'].iloc[-100:], name="Ár", line=dict(color="#00ffcc", width=3)))
    fig.add_trace(go.Scatter(x=df1.index[-100:], y=df1['Upper'].iloc[-100:], name="Felső", line=dict(color="#ffffff", dash="dot", opacity=0.3)))
    fig.add_trace(go.Scatter(x=df1.index[-100:], y=df1['Lower'].iloc[-100:], name="Alsó", line=dict(color="#ffffff", dash="dot", opacity=0.3)))
    fig.update_layout(template="plotly_dark", height=450, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117')
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("Várakozás a vasárnap éjféli nyitásra. Az adatok ekkor frissülnek élőben.")

