import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import time
import json
import os

# =================================================================
# 1. ÁLLANDÓ MEMÓRIA
# =================================================================
DATA_FILE = "brent_commander_v3.json"

def save_state():
    data = {
        "wallet": st.session_state.wallet,
        "history": st.session_state.history,
        "active_trade": st.session_state.active_trade,
        "ai_broker": st.session_state.ai_broker
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
                st.session_state.wallet = d.get("wallet", 1000000.0)
                st.session_state.history = d.get("history", [])
                st.session_state.active_trade = d.get("active_trade", None)
                st.session_state.ai_broker = d.get("ai_broker", False)
        except: pass

# =================================================================
# 2. KERESKEDÉSI LOGIKA (75% TÉT)
# =================================================================
def manage_trade(action, side, price):
    if action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        
        profit_ft = t['amt'] * pnl
        st.session_state.wallet += (t['amt'] + profit_ft)
        st.session_state.history.append({
            'Idő': datetime.now().strftime("%H:%M:%S"), 
            'Irány': t['side'],
            'Profit': f"{profit_ft:,.0f} Ft",
            'Ár': f"${price:.2f}"
        })
        st.session_state.active_trade = None
        save_state()

    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.wallet -= inv
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': str(datetime.now())}
        save_state()

# =================================================================
# 3. DASHBOARD & MOBIL OPTIMALIZÁLÁS
# =================================================================
st.set_page_config(page_title="BRENT MOBILE COMMANDER", layout="wide")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
    st.session_state.history = []
    st.session_state.active_trade = None
    st.session_state.ai_broker = False
    load_state()

# CSS A KÖZÉPRE RENDEZÉSHEZ (MOBILON IS)
st.markdown("""
    <style>
    /* A kapcsoló (toggle) konténerének kényszerítése középre */
    div[data-testid="stCheckbox"] {
        display: flex;
        justify-content: center;
        width: 100%;
    }
    .stToggle {
        display: flex;
        justify-content: center;
    }
    .main-header {
        background: #0e1117;
        border-bottom: 2px solid #00d4ff;
        padding: 10px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ADATOK LEKÉRÉSE
live_data = yf.download("BZ=F", period="1d", interval="1m", progress=False)
if isinstance(live_data.columns, pd.MultiIndex): live_data.columns = live_data.columns.droplevel(1)

if not live_data.empty:
    curr_p = float(live_data['Close'].iloc[-1])
    ema_fast = live_data['Close'].ewm(span=12, adjust=False).mean()
    ema_slow = live_data['Close'].ewm(span=26, adjust=False).mean()

    # FEJLÉC
    st.markdown(f'<div class="main-header"><h2 style="color:white; margin:0;">💰 {st.session_state.wallet:,.0f} Ft</h2><p style="color:#00d4ff; margin:0;">BRENT: ${curr_p:.2f}</p></div>', unsafe_allow_html=True)

    st.write("") # Térköz

    # --- A KÖZÉPRE RENDEZETT KAPCSOLÓ ---
    st.session_state.ai_broker = st.toggle("🤖 ROBOT AUTO-PILOT", value=st.session_state.ai_broker)
    save_state()

    # ROBOT LOGIKA
    if st.session_state.ai_broker:
        target_side = "LONG" if ema_fast.iloc[-1] > ema_slow.iloc[-1] else "SHORT"
        if not st.session_state.active_trade:
            manage_trade("OPEN", target_side, curr_p)
        elif st.session_state.active_trade['side'] != target_side:
            manage_trade("CLOSE", None, curr_p)
            manage_trade("OPEN", target_side, curr_p)

    # GRAFIKON
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=live_data.index, open=live_data['Open'], high=live_data['High'], low=live_data['Low'], close=live_data['Close'], name='Ár'))
    fig.add_trace(go.Scatter(x=live_data.index, y=ema_fast, name='Gyors', line=dict(color='#00d4ff', width=1)))
    fig.add_trace(go.Scatter(x=live_data.index, y=ema_slow, name='Lassú', line=dict(color='#ffaa00', width=1)))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        fig.add_hline(y=t['entry'], line_dash="dash", line_color=color)

    fig.update_layout(template="plotly_dark", height=400, xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=5, b=5))
    st.plotly_chart(fig, use_container_width=True)

    # VEZÉRLÉS
    c1, c2, c3 = st.columns(3)
    with c1: st.button("🚀 VÉTEL", on_click=manage_trade, args=("OPEN", "LONG", curr_p), use_container_width=True)
    with c2: st.button("📉 ELADÁS", on_click=manage_trade, args=("OPEN", "SHORT", curr_p), use_container_width=True)
    with c3: st.button("❌ ZÁRÁS", on_click=manage_trade, args=("CLOSE", None, curr_p), use_container_width=True)

    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(5)
    st.rerun()
