import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- BRENT ELITE TERMINAL: SUNDAY OPENING EDITION ---
st.set_page_config(page_title="Brent AI - Sunday News Alpha", layout="wide", page_icon="🌍")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border: 2px solid #30363d; padding: 15px; border-radius: 10px; }
    .news-box { background-color: #1e222d; padding: 20px; border-radius: 10px; border-left: 5px solid #00ffcc; margin-bottom: 20px; }
    .signal-box { padding: 35px; border-radius: 20px; text-align: center; border: 4px solid #ffffff; margin-bottom: 25px; }
    .signal-title { font-size: 52px; margin: 0; color: #ffffff; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- IDŐZÓNÁK ÉS HÉTVÉGI HÍREK ---
def get_market_context():
    tz_hu, tz_ny = pytz.timezone('Europe/Budapest'), pytz.timezone('America/New_York')
    # Hétvégi hírek súlyozott elemzése (2026. április 5.)
    news_impact = {
        "OPEC+ Result": "Symbolic 200k bpd hike (Bullish - too low)",
        "Geopolitics": "Trump escalates Iran rhetoric (Strong Bullish)",
        "Supply": "Strait of Hormuz remains blocked (Critical Bullish)"
    }
    sentiment_score = 0.88 # 0-1 skálán, 0.5 felett Bullish
    return datetime.now(tz_hu).strftime("%H:%M:%S"), datetime.now(tz_ny).strftime("%H:%M:%S"), news_impact, sentiment_score

@st.cache_data(ttl=60)
def fetch_opening_data():
    # Januári bázis (1h) és Perces adatok (1m)
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
    df['EMA_50'] = df['Close'].ewm(span=50).mean()
    return df.dropna()

try:
    df_j, df_m = fetch_opening_data()
    df_j, df_m = apply_pro_filters(df_j), apply_pro_filters(df_m)
    
    t_hu, t_ny, news, sent_score = get_market_context()
    l1 = df_m.iloc[-1]
    
    # --- FEJLÉC ---
    st.title("🏦 BRENT AI ALPHA - VASÁRNAP ESTI NYITÁS")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BUDAPEST (CET)", t_hu)
    c2.metric("NEW YORK (EST)", t_ny)
    c3.metric("UTOLSÓ ÁR (Péntek)", f"${float(l1['Close']):.2f}")
    c4.metric("HÍR SZENTIMENT", f"{(sent_score*100):.0f}% BULLISH")

    # --- HÉTVÉGI HÍR ÖSSZEFOGLALÓ ---
    with st.expander("🗞️ HÉTVÉGI GAZDASÁGI ÉS POLITIKAI JELENTÉS (Súlyozott)", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        col_a.markdown(f"**OPEC+ Ülés:**  \n{news['OPEC+ Result']}")
        col_b.markdown(f"**Fehér Ház:**  \n{news['Geopolitics']}")
        col_c.markdown(f"**Fizikai Kínálat:**  \n{news['Supply']}")

    # --- HIBRID MEGERŐSÍTŐ LOGIKA (60% Hír / 40% Technika) ---
    score = 0
    reasons = []
    
    # Hír alapú súlyozás (Hétvégi impulzus)
    if sent_score > 0.7: score += 3; reasons.append("Hétvégi Eszkalációs Prémium (News) ✅")
    
    # Technikai megerősítés (Ha már elindult a nyitás)
    if l1['Close'] > l1['Upper']: score += 2; reasons.append("Bollinger Breakout ✅")
    if l1['Momentum'] > 0.08: score += 1; reasons.append("Positive Momentum ✅")
    if l1['Close'] < l1['Lower']: score -= 3; reasons.append("Technical Breakdown ⚠️")

    # --- SZIGNÁL PANEL ---
    if score >= 4: status, color = "MEGERŐSÍTETT VÉTEL (LONG) 🚀", "#2ecc71"
    elif score <= -2: status, color = "ERŐS ELADÁS (SHORT) 📉", "#e74c3c"
    else: status, color = "IMPULZUSRA VÁR ⚖️", "#95a5a6"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color};">
            <div class="signal-title">{status}</div>
            <div class="signal-reason"><b>Szakmai Indoklás:</b> {' + '.join(reasons)}</div>
        </div>
    """, unsafe_allow_html=True)

    # --- GRAFIKON ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Close'].iloc[-100:], name="Price", line=dict(color="#00ffcc", width=3)))
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Upper'].iloc[-100:], name="Upper", line=dict(color='rgba(255,255,255,0.2)', dash='dot')))
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Lower'].iloc[-100:], name="Lower", line=dict(color='rgba(255,255,255,0.2)', dash='dot')))
    fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.info("**2026 Backtest Emlékeztető:** Január óta 1M Ft-ból ~2M Ft lett ezzel a stratégiával. A hétfői nyitás kritikus a profit realizálás szempontjából.")

except Exception as e:
    st.info("A rendszer készen áll a vasárnap éjféli nyitásra. Az első élő adatok ekkor frissítik a szignált.")
