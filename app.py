import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import time
import json
import os
from sklearn.ensemble import RandomForestRegressor

# =================================================================
# 1. ÁLLANDÓ MEMÓRIA
# =================================================================
DATA_FILE = "trading_data_trend.json"

def save_data():
    data = {
        "wallet": st.session_state.wallet,
        "history": st.session_state.history,
        "active_trade": st.session_state.active_trade
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                st.session_state.wallet = data.get("wallet", 1000000.0)
                st.session_state.history = data.get("history", [])
                st.session_state.active_trade = data.get("active_trade", None)
        except: pass

# =================================================================
# 2. KONFIGURÁCIÓ ÉS DESIGN (SZIMMETRIA FIX)
# =================================================================
st.set_page_config(page_title="BRENT AI - MOMENTUM TRADER", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
    load_data()
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'history' not in st.session_state: st.session_state.history = []
if 'ai_broker' not in st.session_state: st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .wallet-header { background: #161b22; border: 2px solid #f1c40f; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .robot-container { background: #1c2128; border: 3px solid #00d4ff; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .signal-box { padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 2px solid white; }
    /* Grafikon konténer fix */
    .plot-container { background: #161b22; border-radius: 15px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 3. TREND-KÖVETŐ MOTOR (SMA + ML)
# =================================================================
@st.cache_data(ttl=3600)
def load_hist():
    df = yf.download("BZ=F", period="1mo", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    return df.dropna()

@st.cache_data(ttl=2)
def load_live():
    df = yf.download("BZ=F", period="1d", interval="1m", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df.index = df.index.tz_localize(None)
    return df.dropna()

def manage_trade(action, side, price):
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': str(datetime.now())}
        save_data()
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        st.session_state.wallet += (t['amt'] * pnl)
        st.session_state.history.append({'Idő': datetime.now().strftime("%H:%M:%S"), 'Profit': f"{t['amt']*pnl:,.0f} Ft"})
        st.session_state.active_trade = None
        save_data()

# =================================================================
# 4. LOGIKA ÉS DASHBOARD
# =================================================================
h, l = load_hist(), load_live()

if not l.empty:
    # TREND SZÁMÍTÁS (Momentum alapú)
    pdf = l.tail(100).copy()
    curr_p = float(pdf['Close'].iloc[-1])
    sma_short = pdf['Close'].rolling(window=10).mean().iloc[-1] # 10 perces átlag
    sma_long = pdf['Close'].rolling(window=30).mean().iloc[-1]  # 30 perces átlag
    
    # Stratégia: Ha az ár az átlag felett van és emelkedik -> VÉTEL
    # Ha az ár az átlag alatt van és esik -> ELADÁS
    trend_up = curr_p > sma_short and sma_short > sma_long
    trend_down = curr_p < sma_short and sma_short < sma_long

    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if trend_up: manage_trade("OPEN", "LONG", curr_p)
            elif trend_down: manage_trade("OPEN", "SHORT", curr_p)
        else:
            # Csak akkor száll ki, ha a trend határozottan megfordul
            side = st.session_state.active_trade['side']
            if (side == "LONG" and curr_p < sma_long) or (side == "SHORT" and curr_p > sma_long):
                manage_trade("CLOSE", None, curr_p)

    # UI: EGYENLEG
    st.markdown(f'<div class="wallet-header"><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1><small style="color:#f1c40f;">TREND-KÖVETŐ STRATÉGIA</small></div>', unsafe_allow_html=True)
    
    # UI: ROBOT PANEL (GARANTÁLT KÖZÉPPONT)
    st.markdown('<div class="robot-container"><h3 style="color:#00d4ff; margin-bottom:15px;">🤖 ROBOT VEZÉRLÉS</h3>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.session_state.ai_broker = st.toggle("STATUS", value=st.session_state.ai_broker)
    st.markdown('</div>', unsafe_allow_html=True)

    # UI: SZIGNÁL
    sig_text = "ERŐS EMELKEDÉS 🚀" if trend_up else "ERŐS LEJTMENET 📉" if trend_down else "OLDALAZÁS ⚖️"
    sig_col = "#2ecc71" if trend_up else "#e74c3c" if trend_down else "#7f8c8d"
    st.markdown(f'<div class="signal-box" style="background-color:{sig_col};"><b>{sig_text}</b></div>', unsafe_allow_html=True)

    # GRAFIKON KONSTRUKCIÓ (STABIL VERZIÓ)
    fig = go.Figure()
    chart_df = l.tail(60)
    
    # Alap árfolyam
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['Close'], mode='lines', line=dict(color='white', width=1), name='Ár'))
    
    # Aktív trade színes követése
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        entry_dt = pd.to_datetime(t['time'])
        trade_slice = chart_df[chart_df.index >= entry_dt]
        t_color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        
        if not trade_slice.empty:
            # Vastag vonal a belépéstől
            fig.add_trace(go.Scatter(x=trade_slice.index, y=trade_slice['Close'], mode='lines+markers', line=dict(color=t_color, width=6), marker=dict(size=4)))
            # Belépési pont
            fig.add_trace(go.Scatter(x=[trade_slice.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=15, symbol='star')))

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # MANUÁLIS GOMBOK
    m1, m2, m3 = st.columns(3)
    with m1: 
        if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with m2: 
        if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with m3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # NAPLÓ
    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(5)
    st.rerun()
