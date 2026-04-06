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
# 1. ÁLLANDÓ MEMÓRIA (JSON ADATBÁZIS)
# =================================================================
DATA_FILE = "brent_commander_v2.json"

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
# 2. ADAPTÍV ELEMZŐ (GYORSÍTOTT EMA)
# =================================================================
@st.cache_data(ttl=3600)
def analyze_6_months():
    df = yf.download("BZ=F", period="6mo", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df = df.dropna()
    # Exponenciális átlagok a gyorsabb reakcióért
    df['EMA5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['EMA15'] = df['Close'].ewm(span=15, adjust=False).mean()
    return df

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK (75% TÉT + FORDÍTÁS)
# =================================================================
def manage_trade(action, side, price):
    # ZÁRÁS LOGIKA
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

    # NYITÁS LOGIKA
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.wallet -= inv
        st.session_state.active_trade = {
            'side': side, 
            'entry': price, 
            'amt': inv, 
            'time': str(datetime.now())
        }
        save_state()

# =================================================================
# 4. DASHBOARD KONFIGURÁCIÓ
# =================================================================
st.set_page_config(page_title="BRENT AI - COMMAND CENTER V2", layout="wide")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
    st.session_state.history = []
    st.session_state.active_trade = None
    st.session_state.ai_broker = False
    load_state()

st.markdown("""
    <style>
    .main { background-color: #0d1117; }
    .wallet-box { background: #161b22; border: 2px solid #00d4ff; border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Élő adatok letöltése
live_data = yf.download("BZ=F", period="1d", interval="1m", progress=False)
if isinstance(live_data.columns, pd.MultiIndex): live_data.columns = live_data.columns.droplevel(1)

if not live_data.empty:
    curr_p = float(live_data['Close'].iloc[-1])
    # Gyorsított EMA indikátorok (5 és 15 perces)
    ema5 = live_data['Close'].ewm(span=5, adjust=False).mean().iloc[-1]
    ema15 = live_data['Close'].ewm(span=15, adjust=False).mean().iloc[-1]

    # UI: Egyenleg és Ár
    st.markdown(f'<div class="wallet-box"><h1 style="color:white; margin:0;">{st.session_state.wallet:,.0f} Ft</h1><p style="color:#00d4ff; margin:0;">BRENT AKTUÁL: ${curr_p:.2f} | EMA5: ${ema5:.2f}</p></div>', unsafe_allow_html=True)

    # UI: Robot kapcsoló
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.session_state.ai_broker = st.toggle("🤖 AGRESSZÍV ROBOT AKTÍV", value=st.session_state.ai_broker)
        save_state()

    # --- ROBOT AUTOMATA LOGIKA (AZONNALI FORDÍTÁSSAL) ---
    if st.session_state.ai_broker:
        target_side = "LONG" if ema5 > ema15 else "SHORT"
        
        if not st.session_state.active_trade:
            # Első belépés
            manage_trade("OPEN", target_side, curr_p)
        else:
            # Ha az irány megváltozott: ZÁRÁS + AZONNALI ÚJRANYITÁS
            if st.session_state.active_trade['side'] != target_side:
                manage_trade("CLOSE", None, curr_p)
                manage_trade("OPEN", target_side, curr_p)

    # UI: Grafikon
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=live_data.index, y=live_data['Close'], mode='lines', name='Ár', line=dict(color='white', width=1.5)))
    fig.add_trace(go.Scatter(x=live_data.index, y=live_data['Close'].ewm(span=5).mean(), mode='lines', name='EMA5', line=dict(color='#00d4ff', width=1, dash='dot')))
    
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        t_color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        fig.add_annotation(x=live_data.index[-1], y=curr_p, text=f"AKTÍV {t['side']}", showarrow=True, arrowhead=1, bgcolor=t_color)

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10,r=10,t=10,b=10), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # UI: Manuális vezérlés
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🚀 VÉTEL (75%)", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with c2: 
        if st.button("📉 ELADÁS (75%)", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with c3: 
        if st.button("❌ KÉZI ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # UI: Napló
    if st.session_state.history:
        st.write("### 📝 Tranzakciós Napló")
        st.table(pd.DataFrame(st.session_state.history).tail(5))

    time.sleep(5)
    st.rerun()
