import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz
import time
from sklearn.ensemble import RandomForestRegressor

# =================================================================
# 1. KONFIGURÁCIÓ ÉS ÁLLANDÓ MEMÓRIA
# =================================================================
st.set_page_config(page_title="BRENT AI - PERMANENT TRADER", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
if 'active_trade' not in st.session_state:
    st.session_state.active_trade = None
if 'history' not in st.session_state:
    st.session_state.history = []
if 'ai_broker' not in st.session_state:
    st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 10px; border-radius: 10px; text-align: center; }
    .stat-label { color: #FFFFFF; font-size: 11px; font-weight: 800; text-transform: uppercase; display: block; }
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; display: block; }
    
    .wallet-header { background: #161b22; border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 10px; }
    .robot-header { background: #1c2128; border: 2px solid #00d4ff; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 10px; }
    
    /* SZIMMETRIKUS KÖZÉPSŐ KAPCSOLÓ */
    .switch-container { display: flex; justify-content: center; align-items: center; gap: 40px; margin: 20px 0; }
    .stToggle > div { transform: scale(2.8); }
    
    .signal-box { padding: 20px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 30px !important; color: #ffffff !important; font-weight: 900; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS ML MOTOR (GRAFIKON FIX)
# =================================================================
@st.cache_data(ttl=10)
def load_market_data():
    try:
        # Friss adatok letöltése
        ticker = yf.Ticker("BZ=F")
        df = ticker.history(period="1d", interval="1m")
        if df.empty: return None
        # Időzóna eltávolítása a plotly kompatibilitáshoz
        df.index = df.index.tz_localize(None)
        return df
    except: return None

def get_ai_prediction(df):
    if len(df) < 20: return float(df['Close'].iloc[-1])
    data = df.tail(80).copy()
    data['Target'] = data['Close'].shift(-1)
    data = data.dropna()
    X = data[['Open', 'High', 'Low', 'Close']].values
    y = data['Target'].values
    model = RandomForestRegressor(n_estimators=50, random_state=42).fit(X[:-1], y[:-1])
    prediction = model.predict(X[-1].reshape(1, -1))
    return float(prediction[0])

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK
# =================================================================
def manage_trade(action, side, price, risk=75):
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * (risk / 100)
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': datetime.now()}
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        st.session_state.wallet += (t['amt'] * pnl)
        st.session_state.history.append({'Idő': datetime.now().strftime("%H:%M"), 'Profit': f"{(t['amt'] * pnl):+.0f} Ft"})
        st.session_state.active_trade = None

# =================================================================
# 4. MEGJELENÍTÉS
# =================================================================
df = load_market_data()

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    pred_p = get_ai_prediction(df)
    buy_pct = 100 if pred_p > curr_p else 0
    sell_pct = 100 - buy_pct

    # --- 1. EGYENLEG ---
    st.markdown(f'<div class="wallet-header"><h3 style="color:#f1c40f;margin:0;">VIRTUÁLIS EGYENLEG</h3><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>', unsafe_allow_html=True)
    
    # --- 2. ROBOT BRÓKER SZIMMETRIKUS MEZŐ ---
    st.markdown('<div class="robot-header"><h3 style="color:#00d4ff;margin:0;font-size:18px;">🤖 ROBOT BRÓKER VEZÉRLÉS</h3>', unsafe_allow_html=True)
    
    # Középre zárt elrendezés
    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_mid:
        st.markdown('<div class="switch-container">', unsafe_allow_html=True)
        c_ki, c_sw, c_be = st.columns([1, 2, 1])
        with c_ki: st.markdown('<p style="color:#e74c3c; font-size:24px; font-weight:900; text-align:right; margin-top:35px;">KI</p>', unsafe_allow_html=True)
        with c_sw: st.session_state.ai_broker = st.toggle("", value=st.session_state.ai_broker, label_visibility="collapsed")
        with c_be: st.markdown('<p style="color:#2ecc71; font-size:24px; font-weight:900; text-align:left; margin-top:35px;">BE</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- 3. SZIGNÁL ---
    color = "#2ecc71" if buy_pct > 50 else "#e74c3c"
    st.markdown(f'<div class="signal-box" style="background-color: {color};"><div class="signal-title">{"VÉTEL! 🚀" if buy_pct > 50 else "ELADÁS! 📉"} ({max(buy_pct, sell_pct)}%)</div></div>', unsafe_allow_html=True)

    # --- 4. MANUÁLIS GOMBOK ---
    m1, m2, m3 = st.columns(3)
    with m1: 
        if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with m2: 
        if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with m3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # --- 5. 2x3 RÁCS ---
    t_hu = datetime.now(pytz.timezone('Europe/Budapest')).strftime("%H:%M:%S")
    t_ny = datetime.now(pytz.timezone('America/New_York')).strftime("%H:%M:%S")
    st.markdown(f"""<div class="mobile-grid">
        <div class="stat-card"><span class="stat-label">Budapest</span><span class="stat-value">{t_hu}</span></div>
        <div class="stat-card"><span class="stat-label">New York</span><span class="stat-value">{t_ny}</span></div>
        <div class="stat-card"><span class="stat-label">Ár</span><span class="stat-value">${curr_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">Célár</span><span class="stat-value">${pred_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">Vétel</span><span class="stat-value">{buy_pct}%</span></div>
        <div class="stat-card"><span class="stat-label">Eladás</span><span class="stat-value">{sell_pct}%</span></div>
    </div>""", unsafe_allow_html=True)

    # --- 6. GRAFIKON (TELJESEN ÚJRAÍRVA) ---
    fig = go.Figure()
    # Adatok előkészítése
    plot_df = df.tail(60)
    
    # Alap vonal
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Close'], mode='lines', name="Brent Ár", line=dict(color='white', width=2)))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        # Csak a belépés óta tartó szakasz
        active_segment = plot_df[plot_df.index >= t['time']]
        scol = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        
        if not active_segment.empty:
            # Vastag út
            fig.add_trace(go.Scatter(x=active_segment.index, y=active_segment['Close'], mode='lines', line=dict(color=scol, width=10), name="AKTÍV"))
            # Sárga csillag a kezdőpontnál (vagy a legközelebbi adatpontnál)
            fig.add_trace(go.Scatter(x=[active_segment.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=25, symbol='star'), name="START"))

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 7. ROBOT LOGIKA ---
    if st.session_state.ai_broker:
        diff = pred_p - curr_p
        if not st.session_state.active_trade:
            if diff > 0.04: manage_trade("OPEN", "LONG", curr_p)
            elif diff < -0.04: manage_trade("OPEN", "SHORT", curr_p)
        else:
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and diff < -0.01) or (t['side'] == "SHORT" and diff > 0.01):
                manage_trade("CLOSE", None, curr_p)

    time.sleep(5)
    st.rerun()
