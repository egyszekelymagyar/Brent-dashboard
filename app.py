import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz
import time
import requests
import feedparser
from sklearn.ensemble import RandomForestRegressor

# --- 1. ELITE TERMINAL KONFIGURÁCIÓ ---
st.set_page_config(page_title="BRENT AI - ML PREDICTOR PRO", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 12px; border-radius: 10px; text-align: center; }
    .stat-label { color: #FFFFFF !important; font-size: 13px !important; font-weight: 800 !important; text-transform: uppercase; display: block; }
    .stat-value { color: #00ffcc !important; font-size: 20px !important; font-weight: 900 !important; display: block; }
    .signal-box { padding: 35px; border-radius: 20px; text-align: center; border: 4px solid #ffffff; margin-bottom: 20px; }
    .signal-title { font-size: 45px !important; color: #ffffff !important; font-weight: 900 !important; text-shadow: 2px 2px 4px #000; margin: 0 !important; }
    .ml-card { background: linear-gradient(135deg, #1e2631 0%, #0e1117 100%); border: 2px solid #f1c40f; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ADATKEZELÉS ---
@st.cache_data(ttl=60)
def load_multi_data():
    intervals = {"1m": "1d", "5m": "5d", "1h": "1mo"}
    data = {}
    for tf, prd in intervals.items():
        df = yf.download("BZ=F", period=prd, interval=tf, progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        data[tf] = df.dropna()
    return data

def calc_indicators(df):
    df = df.copy()
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['Upper'] = df['SMA_20'] + (df['Close'].rolling(20).std() * 2)
    df['Lower'] = df['SMA_20'] - (df['Close'].rolling(20).std() * 2)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    return df.dropna()

# --- 3. ML MODUL ---
def ml_predict_price(df):
    data = df.copy().tail(200)
    data['Target'] = data['Close'].shift(-1)
    data['SMA5'] = data['Close'].rolling(5).mean()
    data['SMA10'] = data['Close'].rolling(10).mean()
    data = data.dropna()
    features = ['Open', 'High', 'Low', 'Close', 'SMA5', 'SMA10']
    X, y = data[features].values, data['Target'].values
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X[:-1], y[:-1])
    return model.predict(X[-1].reshape(1, -1))[0]

# --- 4. SZENTIMENT ---
@st.cache_data(ttl=300)
def get_live_sentiment():
    feed = feedparser.parse("https://google.com")
    score = 0.5
    bullish = ['rise', 'cut', 'shortage', 'higher', 'demand', 'war', 'conflict']
    bearish = ['drop', 'increase', 'glut', 'surplus', 'down', 'recession']
    for entry in feed.entries[:10]:
        txt = entry.title.lower()
        for w in bullish: 
            if w in txt: score += 0.05
        for w in bearish: 
            if w in txt: score -= 0.05
    return min(max(score, 0.1), 0.95)

# --- 5. FŐ PROGRAM ---
try:
    all_data = load_multi_data()
    df_5m = calc_indicators(all_data["5m"])
    df_1h = calc_indicators(all_data["1h"])
    
    predicted_next_price = ml_predict_price(df_5m)
    sent_score = get_live_sentiment()
    
    latest = df_5m.iloc[-1]
    curr_price = latest['Close']
    
    tz_hu, tz_ny = pytz.timezone('Europe/Budapest'), pytz.timezone('America/New_York')
    t_hu, t_ny = datetime.now(tz_hu).strftime("%H:%M:%S"), datetime.now(tz_ny).strftime("%H:%M:%S")

    # GRID
    st.markdown(f"""
        <div class="mobile-grid">
            <div class="stat-card"><span class="stat-label">Budapest</span><span class="stat-value">{t_hu}</span></div>
            <div class="stat-card"><span class="stat-label">New York</span><span class="stat-value">{t_ny}</span></div>
            <div class="stat-card"><span class="stat-label">Brent Ár</span><span class="stat-value">${curr_price:.2f}</span></div>
            <div class="stat-card"><span class="stat-label">RSI (5m)</span><span class="stat-value">{latest['RSI']:.1f}</span></div>
        </div>
    """, unsafe_allow_html=True)

    # ML CARD
    ml_diff = predicted_next_price - curr_price
    ml_color = "#2ecc71" if ml_diff > 0 else "#e74c3c"
    st.markdown(f"""
        <div class="ml-card">
            <h4 style="color: #f1c40f; margin: 0;">🤖 SCIKIT-LEARN ML PREDICTION (Next 5m)</h4>
            <h1 style="color: {ml_color}; margin: 5px;">${predicted_next_price:.2f}</h1>
            <p style="margin:0;">Várható elmozdulás: <b>{ml_diff:+.2f} USD</b></p>
        </div>
    """, unsafe_allow_html=True)

    # SIGNAL FUSION
    tech_score = 1 if curr_price > latest['SMA_20'] else 0
    buy_weight = ( (1 if ml_diff > 0 else 0) * 40 ) + (sent_score * 100 * 0.3) + ( tech_score * 30 )
    sell_weight = 100 - buy_weight

    status, color = ("VÉTEL! 🚀", "#2ecc71") if buy_weight > 65 else ("ELADÁS! 📉", "#e74c3c") if sell_weight > 65 else ("VÁRAKOZÁS ⚖️", "#95a5a6")
    st.markdown(f"""<div class="signal-box" style="background-color: {color};">
        <div class="signal-title">{status}</div>
        <div style="color: white; font-weight: bold;">BULLISH: {buy_weight:.1f}% | BEARISH: {sell_weight:.1f}%</div>
    </div>""", unsafe_allow_html=True)

    # GRAFIKON
    fig = go.Figure(go.Scatter(x=df_5m.index[-50:], y=df_5m['Close'].iloc[-50:], line=dict(color="#00ffcc", width=3)))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

    # AUTO REFRESH
    time.sleep(30)
    st.rerun()

except Exception as e:
    st.info("Piacnyitás várakozás...")
