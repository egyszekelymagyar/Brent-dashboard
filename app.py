import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- ELITE TERMINAL CONFIG ---
st.set_page_config(page_title="Brent AI - Global Alpha", layout="wide", page_icon="🏦")

# HIGH-CONTRAST CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] {
        background-color: #1a1c24;
        border: 2px solid #30363d;
        padding: 15px;
        border-radius: 10px;
    }
    div[data-testid="stMetricLabel"] { color: #ffffff !important; font-size: 14px !important; }
    div[data-testid="stMetricValue"] { color: #00ffcc !important; font-size: 24px !important; }
    
    .signal-box {
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        border: 3px solid #ffffff;
        margin-bottom: 20px;
    }
    .signal-title { font-size: 48px; margin: 0; color: #ffffff; font-weight: bold; text-shadow: 2px 2px 4px #000; }
    .signal-reason { font-size: 18px; margin-top: 10px; color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

# --- IDŐZÓNÁK ---
def get_times():
    tz_hu = pytz.timezone('Europe/Budapest')
    tz_ny = pytz.timezone('America/New_York')
    now_hu = datetime.now(tz_hu).strftime("%H:%M:%S")
    now_ny = datetime.now(tz_ny).strftime("%H:%M:%S")
    return now_hu, now_ny

@st.cache_data(ttl=60)
def get_hybrid_data():
    # Január óta tartó trend (1h) és Utolsó 7 nap (1m)
    df_jan = yf.download("BZ=F", start="2026-01-01", interval="1h").dropna()
    df_1m = yf.download("BZ=F", period="7d", interval="1m").dropna()
    for d in [df_jan, df_1m]:
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return df_jan, df_1m

def apply_indicators(df, is_minute=False):
    window = 14 if is_minute else 20
    df['SMA'] = df['Close'].rolling(window).mean()
    df['Upper'] = df['SMA'] + (df['Close'].rolling(window).std() * 2.1)
    df['Lower'] = df['SMA'] - (df['Close'].rolling(window).std() * 2.1)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    df['EMA_Trend'] = df['Close'].ewm(span=50).mean()
    return df.dropna()

try:
    df_j, df_m = get_hybrid_data()
    df_j = apply_indicators(df_j, is_minute=False)
    df_m = apply_indicators(df_m, is_minute=True)
    
    t_hu, t_ny = get_times()
    latest_m = df_m.iloc[-1]
    latest_j = df_j.iloc[-1]
    
    # --- FEJLÉC ---
    st.title("🏦 BRENT GLOBAL ALPHA TERMINAL")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("BUDAPEST (CET)", t_hu)
    c2.metric("NEW YORK (EST)", t_ny)
    c3.metric("BRENT ÁR", f"${float(latest_m['Close']):.2f}")
    c4.metric("RSI (1m)", f"{float(latest_m['RSI']):.1f}")
    c5.metric("JAN TREND", "BULLISH" if latest_j['Close'] > latest_j['EMA_Trend'] else "BEARISH")

    # --- HIBRID LOGIKA ---
    score = 0
    reasons = []
    if latest_m['Close'] > latest_m['Upper']: score += 2; reasons.append("1m Breakout")
    if latest_m['RSI'] < 30: score += 1; reasons.append("1m Oversold")
    if latest_j['Close'] > latest_j['EMA_Trend']: score += 1; reasons.append("Jan Trend Alignment")
    else: score -= 1

    # SZIGNÁL PANEL
    if score >= 3: status, color = "ERŐS VÉTEL (LONG) 🚀", "#2ecc71"
    elif score <= -2: status, color = "ERŐS ELADÁS (SHORT) 📉", "#e74c3c"
    else: status, color = "VÁRAKOZÁS / SEMLEGES ⚖️", "#95a5a6"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color};">
            <div class="signal-title">{status}</div>
            <div class="signal-reason"><b>Hibrid Indoklás:</b> {' + '.join(reasons) if reasons else 'Konszolidáció'}</div>
        </div>
    """, unsafe_allow_html=True)

    # --- JAVÍTOTT GRAFIKON (Opacity hiba elhárítva) ---
    st.subheader("📊 Élő Perces Monitor")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m.index[-120:], y=df_m['Close'].iloc[-120:], name="Ár", line=dict(color="#00ffcc", width=3)))
    # Opacity paraméter a Scatter-en belülre került a Line-ból:
    fig.add_trace(go.Scatter(x=df_m.index[-120:], y=df_m['Upper'].iloc[-120:], name="Felső", line=dict(color="#ffffff", dash="dot"), opacity=0.3))
    fig.add_trace(go.Scatter(x=df_m.index[-120:], y=df_m['Lower'].iloc[-120:], name="Alsó", line=dict(color="#ffffff", dash="dot"), opacity=0.3))
    
    fig.update_layout(template="plotly_dark", height=450, paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("Várakozás a vasárnap éjféli nyitásra. Az adatok és a grafikonok ekkor frissülnek élőben.")
