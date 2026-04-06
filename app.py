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
DATA_FILE = "brent_commander_trend.json"

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
# 2. KERESKEDÉSI LOGIKA (75% TÉT + TREND TARTÁS)
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
# 3. DASHBOARD
# =================================================================
st.set_page_config(page_title="BRENT TREND COMMANDER", layout="wide")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
    st.session_state.history = []
    st.session_state.active_trade = None
    st.session_state.ai_broker = False
    load_state()

# Élő adatok (5 perces gyertyák a stabilabb trendért)
live_data = yf.download("BZ=F", period="5d", interval="5m", progress=False)
if isinstance(live_data.columns, pd.MultiIndex): live_data.columns = live_data.columns.droplevel(1)

if not live_data.empty:
    curr_p = float(live_data['Close'].iloc[-1])
    # LASSABB TREND MUTATÓK (EMA 12 és 26)
    ema_fast = live_data['Close'].ewm(span=12, adjust=False).mean().iloc[-1]
    ema_slow = live_data['Close'].ewm(span=26, adjust=False).mean().iloc[-1]

    # UI: Fejléc
    st.markdown(f"""
        <div style="background: #161b22; border: 2px solid #ffaa00; border-radius: 15px; padding: 20px; text-align: center;">
            <h1 style="color:white; margin:0;">{st.session_state.wallet:,.0f} Ft</h1>
            <p style="color:#ffaa00; font-size:20px; margin:0;">BRENT: ${curr_p:.2f} | Trend: {"EMELKEDŐ" if ema_fast > ema_slow else "ESŐ"}</p>
        </div>
        """, unsafe_allow_html=True)

    # UI: Robot kapcsoló
    _, mid, _ = st.columns([1,2,1])
    with mid:
        st.session_state.ai_broker = st.toggle("🤖 TRENDKÖVETŐ ROBOT AKTÍV", value=st.session_state.ai_broker)
        save_state()

    # --- ROBOT LOGIKA (LASSABB VÁLTÁS) ---
    if st.session_state.ai_broker:
        target_side = "LONG" if ema_fast > ema_slow else "SHORT"
        
        if not st.session_state.active_trade:
            manage_trade("OPEN", target_side, curr_p)
        else:
            # Csak akkor vált, ha a trend egyértelműen megfordult (kereszteződés)
            if st.session_state.active_trade['side'] != target_side:
                manage_trade("CLOSE", None, curr_p)
                manage_trade("OPEN", target_side, curr_p)

    # UI: Grafikon
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=live_data.index, y=live_data['Close'], name='Ár', line=dict(color='white')))
    fig.add_trace(go.Scatter(x=live_data.index, y=live_data['Close'].ewm(span=12).mean(), name='Gyors Trend (12)', line=dict(color='#ffaa00', width=1)))
    fig.add_trace(go.Scatter(x=live_data.index, y=live_data['Close'].ewm(span=26).mean(), name='Lassú Trend (26)', line=dict(color='#555', width=1)))
    
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        fig.add_hline(y=t['entry'], line_dash="dot", line_color=color, annotation_text=f"BELÉPÉS: {t['side']}")

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # UI: Kontroll
    c1, c2, c3 = st.columns(3)
    with c1: st.button("🚀 KÉZI VÉTEL", on_click=manage_trade, args=("OPEN", "LONG", curr_p), use_container_width=True)
    with c2: st.button("📉 KÉZI ELADÁS", on_click=manage_trade, args=("OPEN", "SHORT", curr_p), use_container_width=True)
    with c3: st.button("❌ POZÍCIÓ ZÁRÁSA", on_click=manage_trade, args=("CLOSE", None, curr_p), use_container_width=True)

    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(5))

    time.sleep(10) # Lassabb frissítés a stabilabb futáshoz
    st.rerun()
