import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz
import requests

# --- ELITE TERMINAL CONFIG ---
st.set_page_config(page_title="Brent AI - Alpha Confirmation", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border: 2px solid #30363d; padding: 15px; border-radius: 10px; }
    div[data-testid="stMetricLabel"] { color: #ffffff !important; font-size: 14px !important; }
    div[data-testid="stMetricValue"] { color: #00ffcc !important; font-size: 24px !important; }
    .signal-box { padding: 30px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 20px; }
    .signal-title { font-size: 48px; margin: 0; color: #ffffff; font-weight: bold; text-shadow: 2px 2px 4px #000; }
    .signal-reason { font-size: 18px; margin-top: 10px; color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

# --- IDŐZÓNÁK ---
def get_times():
    tz_hu, tz_ny = pytz.timezone('Europe/Budapest'), pytz.timezone('America/New_York')
    return datetime.now(tz_hu).strftime("%H:%M:%S"), datetime.now(tz_ny).strftime("%H:%M:%S")

@st.cache_data(ttl=60)
def get_data():
    df_j = yf.download("BZ=F", start="2026-01-01", interval="1h").dropna()
    df_m = yf.download("BZ=F", period="7d", interval="1m").dropna()
    for d in [df_j, df_m]:
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return df_j, df_m

def apply_filters(df):
    # Alap indikátorok
    df['SMA'] = df['Close'].rolling(20).mean()
    df['Upper'] = df['SMA'] + (df['Close'].rolling(20).std() * 2.1)
    df['Lower'] = df['SMA'] - (df['Close'].rolling(20).std() * 2.1)
    
    # 1. MEGERŐSÍTŐ SZŰRŐ: Momentum (ROC) - Mérjük a mozgás erejét
    df['Momentum'] = df['Close'].diff(3) # 3 perces árváltozás
    
    # 2. MEGERŐSÍTŐ SZŰRŐ: RSI Divergencia szűrés
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # Trend irány (EMA 50)
    df['EMA_Trend'] = df['Close'].ewm(span=50).mean()
    return df.dropna()

try:
    df_j, df_m = get_data()
    df_j, df_m = apply_filters(df_j), apply_filters(df_m)
    
    t_hu, t_ny = get_times()
    l1, l5 = df_m.iloc[-1], df_m.iloc[-5] # Aktuális és 5 perccel ezelőtti adat
    
    # --- FEJLÉC ---
    st.title("🏦 BRENT ALPHA CONFIRMATION TERMINAL")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BUDAPEST (CET)", t_hu)
    c2.metric("NEW YORK (EST)", t_ny)
    c3.metric("BRENT ÁR", f"${float(l1['Close']):.2f}")
    c4.metric("MOMENTUM EREJE", "ERŐS" if abs(l1['Momentum']) > 0.15 else "GYENGE")

    # --- HIBRID DÖNTÉSI LOGIKA MEGERŐSÍTÉSSEL ---
    score = 0
    conf_reasons = []
    
    # VÉTELI MEGERŐSÍTÉS
    if l1['Close'] > l1['Upper'] and l1['Momentum'] > 0.05:
        score += 3; conf_reasons.append("Áttörés + Pozitív Momentum ✅")
    if l1['RSI'] < 35 and l1['Close'] > l1['Lower']:
        score += 1; conf_reasons.append("Visszapattanás Alsó Szintről ✅")
    
    # ELADÁSI (SHORT) MEGERŐSÍTÉS
    if l1['Close'] < l1['Lower'] and l1['Momentum'] < -0.05:
        score -= 3; conf_reasons.append("Letörés + Negatív Momentum ⚠️")
    if l1['RSI'] > 65 and l1['Close'] < l1['Upper']:
        score -= 1; conf_reasons.append("Túlvett Fordulat ⚠️")

    # --- SZIGNÁL PANEL ---
    if score >= 3: status, color = "MEGERŐSÍTETT VÉTEL (LONG) 🚀", "#2ecc71"
    elif score <= -3: status, color = "MEGERŐSÍTETT ELADÁS (SHORT) 📉", "#e74c3c"
    else: status, color = "IMPULZUSRA VÁR ⚖️", "#95a5a6"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color};">
            <div class="signal-title">{status}</div>
            <div class="signal-reason"><b>Szakmai Megerősítés:</b> {' + '.join(conf_reasons) if conf_reasons else 'Nincs tiszta irányú impulzus'}</div>
        </div>
    """, unsafe_allow_html=True)

    # --- GRAFIKON ---
    st.subheader("📊 Élő Monitor & Trendforduló Szűrő")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Close'].iloc[-100:], name="Ár", line=dict(color="#00ffcc", width=3)))
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Upper'].iloc[-100:], name="Ellenállás", line=dict(color='rgba(255, 255, 255, 0.3)', dash='dot')))
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Lower'].iloc[-100:], name="Támasz", line=dict(color='rgba(255, 255, 255, 0.3)', dash='dot')))
    fig.update_layout(template="plotly_dark", height=450, paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("Piacnyitás: Ma éjjel 23:00 / 24:00. Az adatok ekkor frissülnek élőben.")
