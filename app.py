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
DATA_FILE = "brent_commander_final.json"

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
# 2. ADAPTÍV ELEMZŐ (MÚLTBÉLI TANULÁS)
# =================================================================
@st.cache_data(ttl=3600)
def analyze_6_months():
    # Az elmúlt fél év adatai a stratégia kalibrálásához
    df = yf.download("BZ=F", period="6mo", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df = df.dropna()
    # Statisztikai alapú optimum keresés (SMA 10/30 szimuláció)
    df['SMA10'] = df['Close'].rolling(window=10).mean()
    df['SMA30'] = df['Close'].rolling(window=30).mean()
    return df

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK (75% TÉT)
# =================================================================
def manage_trade(action, side, price):
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': str(datetime.now())}
        save_state()
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        st.session_state.wallet += (t['amt'] * pnl)
        st.session_state.history.append({
            'Idő': datetime.now().strftime("%H:%M:%S"), 
            'Profit': f"{t['amt']*pnl:,.0f} Ft",
            'Ár': f"${price:.2f}"
        })
        st.session_state.active_trade = None
        save_state()

# =================================================================
# 4. DASHBOARD KONFIGURÁCIÓ
# =================================================================
st.set_page_config(page_title="BRENT AI - COMMAND CENTER", layout="wide")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
    st.session_state.history = []
    st.session_state.active_trade = None
    st.session_state.ai_broker = False
    load_state()

# CSS a sötét, tiszta felülethez
st.markdown("""
    <style>
    .main { background-color: #0d1117; }
    .wallet-box { background: #161b22; border: 2px solid #00d4ff; border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 10px; }
    .stToggle { display: flex; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

# Adatok letöltése
hist_analysis = analyze_6_months()
live_data = yf.download("BZ=F", period="1d", interval="1m", progress=False)
if isinstance(live_data.columns, pd.MultiIndex): live_data.columns = live_data.columns.droplevel(1)

if not live_data.empty:
    curr_p = float(live_data['Close'].iloc[-1])
    # Dinamikus indikátorok a $110-os sáv követéséhez
    sma10 = live_data['Close'].rolling(window=10).mean().iloc[-1]
    sma30 = live_data['Close'].rolling(window=30).mean().iloc[-1]

    # --- UI: EGYENLEG ÉS ÁR ---
    st.markdown(f'<div class="wallet-box"><h1 style="color:white; margin:0;">{st.session_state.wallet:,.0f} Ft</h1><p style="color:#00d4ff; margin:0;">BRENT AKTUÁL: ${curr_p:.2f}</p></div>', unsafe_allow_html=True)

    # --- UI: SZIMMETRIKUS ROBOT KAPCSOLÓ ---
    # Oszlopok használata a matematikai középponthoz
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.session_state.ai_broker = st.toggle("🤖 ROBOT BRÓKER AKTÍV", value=st.session_state.ai_broker)
        save_state()

    # --- ROBOT AUTOMATA LOGIKA ---
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            # Belépés ha a rövid trend keresztezi a hosszút
            if sma10 > sma30: manage_trade("OPEN", "LONG", curr_p)
            elif sma10 < sma30: manage_trade("OPEN", "SHORT", curr_p)
        else:
            # Kilépés ha a trend megfordul
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and sma10 < sma30) or (t['side'] == "SHORT" and sma10 > sma30):
                manage_trade("CLOSE", None, curr_p)

    # --- UI: GRAFIKON (STABIL PLOTLY MOTOR) ---
    fig = go.Figure()
    # Alap árfolyam
    fig.add_trace(go.Scatter(x=live_data.index, y=live_data['Close'], mode='lines', name='Ár', line=dict(color='white', width=1.5)))
    
    # Aktív kereskedési vonal (Zöld/Piros)
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        # Időbélyeg igazítása a grafikonhoz
        entry_time = pd.to_datetime(t['time']).replace(tzinfo=None)
        trade_data = live_data[live_data.index >= entry_time]
        t_color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        
        if not trade_data.empty:
            fig.add_trace(go.Scatter(x=trade_data.index, y=trade_data['Close'], mode='lines', name='Aktív Trade', line=dict(color=t_color, width=5)))
            # Belépési pont csillaggal
            fig.add_trace(go.Scatter(x=[trade_data.index], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=15, symbol='star'), name='Belépés'))

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10,r=10,t=10,b=10), showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- UI: MANUÁLIS VEZÉRLÉS ---
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🚀 VÉTEL (75%)", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with c2: 
        if st.button("📉 ELADÁS (75%)", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with c3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # --- UI: NAPLÓ ---
    if st.session_state.history:
        st.write("### 📝 Utolsó tranzakciók")
        st.table(pd.DataFrame(st.session_state.history).tail(5))

    # Automatikus frissítés 5 másodpercenként
    time.sleep(5)
    st.rerun()
