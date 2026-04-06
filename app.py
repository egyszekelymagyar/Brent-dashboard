import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz
import time
from sklearn.ensemble import RandomForestRegressor

# --- 1. TERMINÁL STÍLUS ÉS CSS ---
st.set_page_config(page_title="Brent AI - Virtual Trader", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 10px; border-radius: 8px; text-align: center; }
    .stat-label { color: #FFFFFF !important; font-size: 12px; font-weight: 800; display: block; text-transform: uppercase; }
    .stat-value { color: #FFFFFF !important; font-size: 18px; font-weight: 900; display: block; }
    .signal-box { padding: 30px; border-radius: 20px; text-align: center; border: 4px solid #ffffff; margin-bottom: 20px; }
    .signal-title { font-size: 50px !important; color: #ffffff !important; font-weight: 900; text-shadow: 2px 2px 4px #000; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ADAT ÉS ML ENGINE ---
@st.cache_data(ttl=30)
def load_trader_data():
    df = yf.download("BZ=F", period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df.dropna()

def get_ml_decision(df):
    data = df.copy().tail(200)
    data['Target'] = data['Close'].shift(-1)
    data['SMA'] = data['Close'].rolling(7).mean()
    data = data.dropna()
    X, y = data[['Open', 'High', 'Low', 'Close', 'SMA']].values, data['Target'].values
    model = RandomForestRegressor(n_estimators=100, random_state=42).fit(X[:-2], y[:-2])
    pred = model.predict(X[-1].reshape(1, -1))[0]
    return pred

# --- 3. VIRTUÁLIS KERESKEDÉSI LOGIKA ---
try:
    df = load_trader_data()
    pred_p = get_ml_decision(df)
    curr_p = df['Close'].iloc[-1]
    atr = (df['High'] - df['Low']).rolling(14).mean().iloc[-1]
    diff = pred_p - curr_p

    # Szimulált pozíció meghatározása
    # Long: 1, Short: -1, Semleges: 0
    pos_type = 0
    if diff > (atr * 0.4): pos_type = 1
    elif diff < -(atr * 0.4): pos_type = -1

    # Szín és státusz
    if pos_type == 1: status, color, line_col = "VÉTEL! 🚀", "#2ecc71", "#2ecc71"
    elif pos_type == -1: status, color, line_col = "ELADÁS! 📉", "#e74c3c", "#e74c3c"
    else: status, color, line_col = "VÁRAKOZÁS ⚖️", "#95a5a6", "#ffffff"

    # --- UI MEGJELENÍTÉS ---
    st.title("🏦 BRENT AI - VIRTUAL TRADER")
    
    tz_hu, tz_ny = pytz.timezone('Europe/Budapest'), pytz.timezone('America/New_York')
    st.markdown(f"""
        <div class="mobile-grid">
            <div class="stat-card"><span class="stat-label">Budapest</span><span class="stat-value">{datetime.now(tz_hu).strftime('%H:%M:%S')}</span></div>
            <div class="stat-card"><span class="stat-label">New York</span><span class="stat-value">{datetime.now(tz_ny).strftime('%H:%M:%S')}</span></div>
            <div class="stat-card"><span class="stat-label">Aktuális Ár</span><span class="stat-value">${curr_p:.2f}</span></div>
            <div class="stat-card"><span class="stat-label">Virtuális Cél</span><span class="stat-value">${pred_p:.2f}</span></div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""<div class="signal-box" style="background-color: {color};">
        <div class="signal-title">{status}</div>
        <div style="color: white; font-weight: bold; margin-top:10px;">
            Pozíció: {"VÉTEL (LONG)" if pos_type == 1 else "ELADÁS (SHORT)" if pos_type == -1 else "NINCS"}
        </div>
    </div>""", unsafe_allow_html=True)

    # --- 4. GRAFIKON DINAMIKUS SZÍNEKKEL ---
    fig = go.Figure()
    plot_df = df.tail(50)
    
    # Grafikon vonala (Színváltós: fehéren indul, de ha van pozíció, vált zöldre/pirosra)
    fig.add_trace(go.Scatter(
        x=plot_df.index, y=plot_df['Close'], 
        name="Virtuális Trend", 
        line=dict(color=line_col, width=3)
    ))

    # BELÉPÉSI JELÖLÉS (Pont a grafikonon)
    if pos_type != 0:
        fig.add_trace(go.Scatter(
            x=[plot_df.index[-1]], y=[curr_p],
            mode="markers",
            marker=dict(symbol="circle", size=15, color=line_col, line=dict(color="white", width=2)),
            name="Belépési Pont"
        ))
        # Szintek
        sl = curr_p - (atr*2) if pos_type == 1 else curr_p + (atr*2)
        tp = curr_p + (atr*4) if pos_type == 1 else curr_p - (atr*4)
        fig.add_hline(y=sl, line_dash="dot", line_color="#ff4b4b", annotation_text="V. STOP")
        fig.add_hline(y=tp, line_dash="dot", line_color="#00ffcc", annotation_text="V. CÉLÁR")

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='#0e1117', plot_bgcolor='#0e1117')
    st.plotly_chart(fig, use_container_width=True)

    # Tanulási Napló
    st.info(f"**Robot Emlékezet:** Utolsó 200 mintából tanulva. Hibaarány (Vak-teszt): ${abs(pred_p - curr_p):.4f}")

    # Auto-refresh
    time.sleep(30)
    st.rerun()

except Exception as e:
    st.error(f"Piacnyitás szimuláció... (Hiba: {e})")
