import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- BRENT AI - MOBIL-OPTIMALIZÁLT TERMINAL ---
st.set_page_config(page_title="Brent AI - Mobile Grid", layout="wide")

# EXTRA ERŐS CSS: Mobil 2x2 rács és KÉNYSZERÍTETT FEHÉR SZÖVEG
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    
    /* Mobil 2x2 rács konténer */
    .mobile-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 15px;
    }
    
    /* Egyedi kártya stílus */
    .stat-card {
        background-color: #1a1c24;
        border: 1px solid #444;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }
    
    /* KÉNYSZERÍTETT FEHÉR FELIRATOK (Bp, NY, Brent, Vol) */
    .stat-label {
        color: #FFFFFF !important;
        font-size: 13px !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        margin-bottom: 2px;
        text-shadow: 1px 1px 2px #000;
        display: block;
    }
    
    /* KÉNYSZERÍTETT FEHÉR ÉRTÉKEK (Idő, Ár) */
    .stat-value {
        color: #FFFFFF !important;
        font-size: 18px !important;
        font-weight: 900 !important;
        text-shadow: 1px 1px 3px #000;
        display: block;
    }

    /* Nagy szignál box - Mobilra méretezve */
    .signal-box { padding: 25px 10px; border-radius: 15px; text-align: center; border: 3px solid #ffffff; margin-bottom: 15px; }
    .signal-title { 
        font-size: 42px !important; 
        color: #ffffff !important; 
        font-weight: 900 !important; 
        text-shadow: 2px 2px 4px #000000 !important;
        margin: 0 !important;
    }
    .signal-sub { 
        font-size: 20px !important; 
        color: #ffffff !important; 
        margin-top: 10px !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

def get_market_info():
    tz_hu, tz_ny = pytz.timezone('Europe/Budapest'), pytz.timezone('America/New_York')
    geo_score = 0.88 
    news_summary = "OPEC+ jelképes emelés | Hormuzi blokád"
    return datetime.now(tz_hu).strftime("%H:%M:%S"), datetime.now(tz_ny).strftime("%H:%M:%S"), geo_score, news_summary

@st.cache_data(ttl=60)
def fetch_data():
    df_m = yf.download("BZ=F", period="7d", interval="1m").dropna()
    if isinstance(df_m.columns, pd.MultiIndex): df_m.columns = df_m.columns.get_level_values(0)
    return df_m

try:
    df_m = fetch_data()
    l1 = df_m.iloc[-1]
    t_hu, t_ny, geo_score, news_txt = get_market_info()
    
    # Számítások
    sma_20 = df_m['Close'].rolling(20).mean().iloc[-1]
    atr = (df_m['High'] - df_m['Low']).rolling(14).mean().iloc[-1]
    buy_pct = (geo_score * 55) + ( (100 if l1['Close'] > sma_20 else 0) * 0.25) + (40 * 0.20)
    sell_pct = 100 - buy_pct

    # --- MOBIL 2x2 RÁCS ---
    st.markdown(f"""
        <div class="mobile-container">
            <div class="stat-card">
                <span class="stat-label">Budapest</span>
                <span class="stat-value">{t_hu}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">New York</span>
                <span class="stat-value">{t_ny}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Brent Olaj</span>
                <span class="stat-value">${l1['Close']:.2f}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Volatilitás</span>
                <span class="stat-value">${atr:.2f}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- SZIGNÁL PANEL ---
    if buy_pct > 65: status, color = "VÉTEL! 🚀", "#2ecc71"
    elif sell_pct > 65: status, color = "ELADÁS! 📉", "#e74c3c"
    else: status, color = "VÁRAKOZÁS ⚖️", "#95a5a6"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color};">
            <div class="signal-title">{status}</div>
            <div class="signal-sub">VÉTEL: {buy_pct:.1f}% | ELADÁS: {sell_pct:.1f}%</div>
        </div>
    """, unsafe_allow_html=True)

    # Célárak mobilon
    st.write(f"🎯 **Cél:** ${l1['Close'] + (atr*5):.2f} | 🛡️ **Stop:** ${l1['Close'] - (atr*2.5):.2f}")

    # GRAFIKON (Mobilra optimalizált magasság)
    fig = go.Figure(go.Scatter(x=df_m.index[-60:], y=df_m['Close'].iloc[-60:], line=dict(color="#00ffcc", width=2)))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

except Exception as e:
    st.info("Piacnyitás: Vasárnap 23:00 / 24:00. Az adatok ekkor frissülnek.")
