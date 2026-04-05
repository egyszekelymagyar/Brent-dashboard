import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- BRENT ELITE TERMINAL: FINAL HIGH-CONTRAST VERSION ---
st.set_page_config(page_title="Brent AI - Sunday News Alpha", layout="wide", page_icon="🌍")

# FIXÁLT CSS: Minden szöveg kényszerített fehér, árnyékkal a maximális olvashatóságért
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border: 2px solid #30363d; padding: 15px; border-radius: 10px; }
    div[data-testid="stMetricLabel"] { color: #ffffff !important; font-size: 16px !important; }
    div[data-testid="stMetricValue"] { color: #00ffcc !important; font-size: 26px !important; font-weight: bold !important; }
    
    /* Nagy szignál box kényszerített fehér szöveggel */
    .signal-box { padding: 35px; border-radius: 20px; text-align: center; border: 4px solid #ffffff; margin-bottom: 25px; }
    .signal-title { 
        font-size: 52px !important; 
        margin: 0 !important; 
        color: #ffffff !important; 
        font-weight: bold !important;
        text-shadow: 2px 2px 5px rgba(0,0,0,0.8) !important;
    }
    .signal-reason { 
        font-size: 20px !important; 
        margin-top: 15px !important; 
        color: #ffffff !important;
        text-shadow: 1px 1px 3px rgba(0,0,0,0.8) !important;
    }
    b { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

# --- IDŐZÓNÁK ÉS KONTEXTUS ---
def get_market_context():
    tz_hu, tz_ny = pytz.timezone('Europe/Budapest'), pytz.timezone('America/New_York')
    news_impact = {
        "OPEC+": "Jelképes 200k hordós emelés (Kevés, Bullish hatás)",
        "Geopolitika": "Trump keményebb fellépést ígér Irán ellen (Erős Bullish)",
        "Kínálat": "A Hormuzi-szoros továbbra is blokád alatt (Kritikus Bullish)"
    }
    sentiment_score = 0.88 
    return datetime.now(tz_hu).strftime("%H:%M:%S"), datetime.now(tz_ny).strftime("%H:%M:%S"), news_impact, sentiment_score

@st.cache_data(ttl=60)
def fetch_opening_data():
    df_jan = yf.download("BZ=F", start="2026-01-01", interval="1h").dropna()
    df_1m = yf.download("BZ=F", period="5d", interval="1m").dropna()
    for d in [df_jan, df_1m]:
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return df_jan, df_1m

def apply_pro_filters(df):
    df['SMA'] = df['Close'].rolling(20).mean()
    df['Upper'] = df['SMA'] + (df['Close'].rolling(20).std() * 2.1)
    df['Lower'] = df['SMA'] - (df['Close'].rolling(20).std() * 2.1)
    df['Momentum'] = df['Close'].diff(3)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    return df.dropna()

try:
    df_j, df_m = fetch_opening_data()
    df_j, df_m = apply_pro_filters(df_j), apply_pro_filters(df_m)
    
    t_hu, t_ny, news, sent_score = get_market_context()
    l1 = df_m.iloc[-1]
    
    # --- FEJLÉC ---
    st.title("🏦 BRENT AI ALPHA - TERMINAL")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BUDAPEST (CET)", t_hu)
    c2.metric("NEW YORK (EST)", t_ny)
    c3.metric("BRENT ÁR (Péntek)", f"${float(l1['Close']):.2f}")
    c4.metric("HÍR SZENTIMENT", f"{(sent_score*100):.0f}% BULLISH")

    # --- HÍREK ---
    with st.expander("🗞️ HÉTVÉGI JELENTÉS (Súlyozott elemzés)", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        col_a.write(f"**OPEC+:** {news['OPEC+']}")
        col_b.write(f"**Politika:** {news['Geopolitika']}")
        col_c.write(f"**Fizikai:** {news['Kínálat']}")

    # --- LOGIKA ---
    score = 0
    reasons = []
    if sent_score > 0.7: score += 3; reasons.append("Hír-alapú Emelkedő Nyomás ✅")
    if l1['Close'] > l1['Upper']: score += 2; reasons.append("Technikai Kitörés ✅")
    if l1['Momentum'] > 0.08: score += 1; reasons.append("Erős Momentum ✅")

    # SZIGNÁL PANEL (SZÍNEK + FEHÉR SZÖVEG)
    if score >= 4: status, color = "ERŐS VÉTEL (LONG) 🚀", "#2ecc71"
    elif score <= -2: status, color = "ERŐS ELADÁS (SHORT) 📉", "#e74c3c"
    else: status, color = "IMPULZUSRA VÁR ⚖️", "#95a5a6"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color};">
            <div class="signal-title">{status}</div>
            <div class="signal-reason"><b>Szakmai Indoklás:</b> {' + '.join(reasons) if reasons else 'Konszolidáció / Nincs tiszta jel'}</div>
        </div>
    """, unsafe_allow_html=True)

    # GRAFIKON
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Close'].iloc[-100:], name="Ár", line=dict(color="#00ffcc", width=3)))
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Upper'].iloc[-100:], name="Ellenállás", line=dict(color='rgba(255,255,255,0.2)', dash='dot')))
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Lower'].iloc[-100:], name="Támasz", line=dict(color='rgba(255,255,255,0.2)', dash='dot')))
    fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.info("Piacnyitás: Ma éjjel (Vasárnap) 23:00 - 24:00 között.")

except Exception as e:
    st.info("A rendszer készen áll az éjféli nyitásra. Az adatok ekkor frissülnek élőben.")
