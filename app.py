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
if 'last_exit' not in st.session_state:
    st.session_state.last_exit = None

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 10px; border-radius: 10px; text-align: center; }
    .stat-label { color: #FFFFFF; font-size: 11px; font-weight: 800; text-transform: uppercase; display: block; }
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; display: block; }
    .wallet-header { background: linear-gradient(90deg, #161b22, #232d39); border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 10px; }
    
    /* ROBOT BRÓKER MEZŐ */
    .ai-container { background-color: #1a1c24; padding: 30px; border-radius: 20px; border: 4px solid #00d4ff; text-align: center; margin-bottom: 20px; }
    .robot-title { font-size: 32px; font-weight: 900; color: #00d4ff; margin-bottom: 10px; }
    
    /* ÓRIÁS KAPCSOLÓ */
    .switch-text { font-size: 24px; font-weight: 900; vertical-align: middle; }
    .stToggle > div { transform: scale(3.5); margin: 45px 0; }
    
    .signal-box { padding: 20px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 30px !important; color: #ffffff !important; font-weight: 900; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS ML MOTOR (JAVÍTVA)
# =================================================================
@st.cache_data(ttl=15)
def load_market_data():
    try:
        df = yf.download("BZ=F", period="1d", interval="1m", progress=False)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.index = df.index.tz_localize(None)
        return df.dropna()
    except: return None

def get_ai_prediction(df):
    if len(df) < 20: return float(df['Close'].iloc[-1])
    data = df.tail(100).copy()
    data['Target'] = data['Close'].shift(-1)
    data = data.dropna()
    X, y = data[['Open', 'High', 'Low', 'Close']].values, data['Target'].values
    model = RandomForestRegressor(n_estimators=50, random_state=42).fit(X[:-1], y[:-1])
    prediction = model.predict(X[-1].reshape(1, -1))
    return float(prediction[0]) # FIXED: Tömb indexelés hozzáadva

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK
# =================================================================
def manage_trade(action, side, price, risk=75):
    if action == "OPEN" and not st.session_state.active_trade:
        investment = st.session_state.wallet * (risk / 100)
        st.session_state.active_trade = {
            'side': side, 'entry': price, 'amt': investment, 'time': datetime.now()
        }
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl_pct = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl_pct *= -1
        profit = t['amt'] * pnl_pct
        st.session_state.wallet += profit
        st.session_state.last_exit = {'time': datetime.now(), 'price': price}
        st.session_state.history.append({
            'Idő': datetime.now().strftime("%H:%M"),
            'Típus': t['side'],
            'Profit': f"{profit:+.0f} Ft",
            'Egyenleg': f"{st.session_state.wallet:,.0f} Ft"
        })
        st.session_state.active_trade = None

# =================================================================
# 4. DASHBOARD
# =================================================================
df = load_market_data()

if df is not None:
    curr_p = df['Close'].iloc[-1]
    pred_p = get_ai_prediction(df)
    diff = pred_p - curr_p
    buy_pct = 100 if pred_p > curr_p else 0
    sell_pct = 100 - buy_pct

    # EGYENLEG
    st.markdown(f"""<div class="wallet-header"><h3 style="color:#f1c40f;margin:0;">VIRTUÁLIS EGYENLEG</h3><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>""", unsafe_allow_html=True)
    
    # ROBOT BRÓKER VEZÉRLŐ (BE/KI)
    st.markdown('<div class="ai-container">', unsafe_allow_html=True)
    st.markdown('<div class="robot-title">🤖 Robot Bróker</div>', unsafe_allow_html=True)
    
    col_l, col_sw, col_r = st.columns([1, 2, 1])
    with col_l: st.markdown('<p class="switch-text" style="color:#e74c3c; text-align:right;">KI</p>', unsafe_allow_html=True)
    with col_sw: st.session_state.ai_broker = st.toggle("", value=st.session_state.ai_broker, label_visibility="collapsed")
    with col_r: st.markdown('<p class="switch-text" style="color:#2ecc71; text-align:left;">BE</p>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with c2: 
        if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with c3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)
    st.markdown('</div>', unsafe_allow_html=True)

    # 2x3 RÁCS ADATOKKAL
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

    # SZIGNÁL PANEL
    status = "VÉTEL! 🚀" if buy_pct > 50 else "ELADÁS! 📉"
    color = "#2ecc71" if buy_pct > 50 else "#e74c3c"
    st.markdown(f"""<div class="signal-box" style="background-color: {color};">
        <div class="signal-title">{status} ({max(buy_pct, sell_pct)}%)</div>
    </div>""", unsafe_allow_html=True)

    # GRAFIKON (BELÉPÉS, TARTÁS, KILÉPÉS)
    fig = go.Figure()
    p_df = df.tail(60)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['Close'], name="Árfolyam", line=dict(color='white', width=1.5)))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        active_mask = p_df.index >= t['time']
        active_segment = p_df[active_mask]
        scol = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        
        if not active_segment.empty:
            # 1. TARTÁS ÚTJA
            fig.add_trace(go.Scatter(x=active_segment.index, y=active_segment['Close'], line=dict(color=scol, width=10), name="Tartás"))
            # 2. BELÉPÉSI PONT
            fig.add_trace(go.Scatter(x=[active_segment.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=22, symbol='star'), name="Belépés"))

    # 3. KILÉPÉSI PONT
    if st.session_state.last_exit:
        le = st.session_state.last_exit
        if le['time'] in p_df.index:
            fig.add_trace(go.Scatter(x=[le['time']], y=[le['price']], mode='markers', marker=dict(color='white', size=15, symbol='x'), name="Kilépés"))

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # AI AUTO LOGIKA
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if diff > 0.05: manage_trade("OPEN", "LONG", curr_p)
            elif diff < -0.05: manage_trade("OPEN", "SHORT", curr_p)
        else:
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and diff < -0.02) or (t['side'] == "SHORT" and diff > 0.02):
                manage_trade("CLOSE", None, curr_p)

    time.sleep(10)
    st.rerun()
