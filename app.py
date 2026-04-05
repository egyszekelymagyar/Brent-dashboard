import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- KONFIGURÁCIÓ ÉS STÍLUS ---
st.set_page_config(page_title="Brent AI - Sentiment Alpha", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border: 2px solid #30363d; padding: 15px; border-radius: 10px; }
    div[data-testid="stMetricLabel"] { color: #ffffff !important; font-size: 14px !important; }
    div[data-testid="stMetricValue"] { color: #00ffcc !important; font-size: 24px !important; }
    .sentiment-card { background-color: #1e222d; padding: 20px; border-radius: 10px; border-left: 5px solid #f1c40f; margin-bottom: 20px; color: white; }
    .signal-box { padding: 35px; border-radius: 20px; text-align: center; border: 4px solid #ffffff; margin-bottom: 25px; }
    .signal-title { font-size: 52px; margin: 0; color: #ffffff !important; font-weight: bold; text-shadow: 2px 2px 4px #000; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. NLP SZENTIMENT LEXIKON (2026-OS KONTEXTUS) ---
SENTIMENT_LEXICON = {
    # BULLISH (Áremelő) kulcsszavak
    "escalation": 0.25, "infrastructure damage": 0.30, "hormuz blockade": 0.40,
    "sanctions": 0.15, "output cut": 0.20, "supply disruption": 0.35, "missile strike": 0.30,
    # BEARISH (Árcsökkentő) kulcsszavak
    "ceasefire": -0.35, "inventory build": -0.15, "output hike": -0.20,
    "de-escalation": -0.30, "demand worry": -0.25, "reopening": -0.20
}

# --- 2. KÜLSŐ PIACI VÁLTOZÓK (EIA & OPEC+) ---
MARKET_EVENTS = {
    "EIA_REPORT": {"day": "Wednesday", "impact": "High Volatility", "last_actual": "5.45M (Build)"},
    "OPEC_MEETING": {"date": "2026-04-05", "result": "Symbolic +206k bpd", "bias": "Bullish (insufficient)"}
}

def analyze_headlines(headlines):
    total_score = 0.5 # Neutrális alap
    found_keywords = []
    for text in headlines:
        for word, val in SENTIMENT_LEXICON.items():
            if word in text.lower():
                total_score += val
                found_keywords.append(word)
    return min(max(total_score, 0), 1), list(set(found_keywords))

@st.cache_data(ttl=60)
def get_advanced_data():
    df_m = yf.download("BZ=F", period="7d", interval="1m").dropna()
    if isinstance(df_m.columns, pd.MultiIndex): df_m.columns = df_m.columns.get_level_values(0)
    return df_m

try:
    df = get_advanced_data()
    # Indikátorok
    df['EMA_20'] = df['Close'].ewm(span=20).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    
    # 3. SZENTIMENT ELEMZÉS (2026. április 5-i hírek alapján)
    live_news = [
        "Trump pledges escalation on Iran infrastructure",
        "OPEC+ agrees to symbolic 206,000 bpd hike for May",
        "Strait of Hormuz remains effectively shut since February",
        "EIA reports unexpected crude inventory build of 5.5M barrels"
    ]
    sent_score, detected = analyze_headlines(live_news)

    # --- UI MEGJELENÍTÉS ---
    st.title("🏦 BRENT AI - ALPHA SENTIMENT TERMINAL")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BRENT ÁR", f"${float(df['Close'].iloc[-1]):.2f}")
    c2.metric("SENTIMENT INDEX", f"{sent_score*100:.0f}%", "BULLISH" if sent_score > 0.5 else "BEARISH")
    c3.metric("EIA KÉSZLET", MARKET_EVENTS["EIA_REPORT"]["last_actual"])
    c4.metric("VOLATILITÁS (ATR)", f"${df['ATR'].iloc[-1]:.2f}")

    # Hír kártya
    with st.container():
        st.markdown(f"""
            <div class="sentiment-card">
                <h4>🗞️ Intelligens Hír-Szentiment Elemzés</h4>
                <p><b>Észlelt piaci faktorok:</b> {', '.join(detected) if detected else 'Nincs releváns kulcsszó'}</p>
                <p><b>Modell megjegyzés:</b> Az OPEC+ emelése jelképes, a háborús kockázat dominál.</p>
            </div>
            """, unsafe_allow_html=True)

    # --- DINAMIKUS SZIGNÁL PANEL (Hír + Technika fúzió) ---
    tech_signal = 1 if df['Close'].iloc[-1] > df['EMA_20'].iloc[-1] else -1
    # Fúziós pontszám: 60% Hír-szentiment, 40% Technikai trend
    fusion_score = (sent_score * 0.6) + ((tech_signal + 1) / 2 * 0.4)

    if fusion_score > 0.65:
        status, color = "ERŐS VÉTEL (LONG) 🚀", "#2ecc71"
    elif fusion_score < 0.35:
        status, color = "ERŐS ELADÁS (SHORT) 📉", "#e74c3c"
    else:
        status, color = "VÁRAKOZÁS / SEMLEGES ⚖️", "#95a5a6"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color};">
            <div class="signal-title" style="color: white !important;">{status}</div>
            <div class="signal-reason" style="color: white !important;"><b>Fúziós Index:</b> {fusion_score:.2f} (Hírek + Technika szinkronizálva)</div>
        </div>
    """, unsafe_allow_html=True)

    # Grafikon
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index[-120:], y=df['Close'].iloc[-120:], name="Ár", line=dict(color="#00ffcc", width=3)))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info(f"Rendszer készenlétben a hétfői nyitásra. (Hiba: {e})")
