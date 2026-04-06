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
DATA_FILE = "trading_data_v2.json"

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
# 2. KONFIGURÁCIÓ ÉS DESIGN
# =================================================================
st.set_page_config(page_title="BRENT AI - TREND TRADER", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
    load_data()
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'history' not in st.session_state: st.session_state.history = []
if 'ai_broker' not in st.session_state: st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .wallet-header { background: #161b22; border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .robot-title-box { background: #1c2128; border: 3px solid #00d4ff; border-bottom: none; padding: 10px; border-radius: 15px 15px 0 0; text-align: center; }
    .robot-toggle-box { background: #1c2128; border: 3px solid #00d4ff; border-top: none; padding: 10px; border-radius: 0 0 15px 15px; margin-bottom: 20px; }
    .signal-box { padding: 20px; border-radius: 15px; text-align: center; border: 3px solid #ffffff; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 3. ADAT ÉS TREND-KÖVETŐ ML MOTOR
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

def get_ai_prediction(h, l):
    try:
        comb = pd.concat([h.tail(50), l.tail(100)])
        comb['Target'] = comb['Close'].shift(-1)
        train = comb.dropna()
        model = RandomForestRegressor(n_estimators=50, random_state=42).fit(
            train[['Open', 'High', 'Low', 'Close']].values, train['Target'].values
        )
        return float(model.predict(l[['Open', 'High', 'Low', 'Close']].iloc[-1:].values)[0])
    except: return float(l['Close'].iloc[-1])

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
# 4. DASHBOARD ÉS LOGIKA
# =================================================================
h, l = load_hist(), load_live()
# AGGRESSZÍV BELÉPÉS, DE TÜRELMESEBB KILÉPÉS (Trend tartás)
entry_threshold = 0.003
exit_threshold = 0.008 

if not l.empty:
    curr_p = float(l['Close'].iloc[-1])
    pred_p = get_ai_prediction(h, l)
    diff = pred_p - curr_p
    
    buy_sig = diff > entry_threshold
    sell_sig = diff < -entry_threshold

    # Robot döntési mechanizmus
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if buy_sig: manage_trade("OPEN", "LONG", curr_p)
            elif sell_sig: manage_trade("OPEN", "SHORT", curr_p)
        else:
            # Kilépés csak akkor, ha a trend határozottan megfordult (exit_threshold)
            side = st.session_state.active_trade['side']
            if (side == "LONG" and diff < -exit_threshold) or (side == "SHORT" and diff > exit_threshold):
                manage_trade("CLOSE", None, curr_p)

    # UI: EGYENLEG
    st.markdown(f'<div class="wallet-header"><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>', unsafe_allow_html=True)
    
    # UI: MATEMATIKAI KÖZÉPPONTÚ KAPCSOLÓ
    st.markdown('<div class="robot-title-box"><span style="color:#00d4ff; font-weight:900;">🤖 ROBOT BRÓKER ÜZEMMÓD</span></div>', unsafe_allow_html=True)
    with st.container():
        # 3 egyenlő oszlop, a középsőben a kapcsolóval
        col_l, col_c, col_r = st.columns([1, 1, 1])
        with col_c:
            st.session_state.ai_broker = st.toggle("STATUS", value=st.session_state.ai_broker, label_visibility="collapsed")
    st.markdown('<div class="robot-toggle-box"></div>', unsafe_allow_html=True)

    # UI: SZIGNÁL
    sig_color = "#2ecc71" if buy_sig else "#e74c3c" if sell_sig else "#7f8c8d"
    st.markdown(f'<div class="signal-box" style="background-color: {sig_color};"><h2 style="color:white;margin:0;font-weight:900;">{"VÉTEL 🚀" if buy_sig else "ELADÁS 📉" if sell_sig else "TREND FIGYELÉS..."}</h2></div>', unsafe_allow_html=True)

    # GRAFIKON KONSTRUKCIÓ (Fixált megjelenítés)
    fig = go.Figure()
    pdf = l.tail(60).copy()
    
    # Halvány háttér árfolyam
    fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], mode='lines', line=dict(color='gray', width=1), opacity=0.4))
    
    # Aktív trade követése
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        entry_dt = pd.to_datetime(t['time'])
        # Csak azokat a pontokat vesszük, amik a belépés óta vannak
        trade_points = pdf[pdf.index >= entry_dt]
        t_color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        
        if not trade_points.empty:
            # Vastag követő vonal
            fig.add_trace(go.Scatter(x=trade_points.index, y=trade_points['Close'], mode='lines+markers', line=dict(color=t_color, width=6), marker=dict(size=4)))
            # Sárga csillag a belépésnél
            fig.add_trace(go.Scatter(x=[trade_points.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=20, symbol='star')))

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10,r=10,t=10,b=10), showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # GOMBOK ÉS INFÓK
    b1, b2, b3 = st.columns(3)
    with b1: 
        if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with b2: 
        if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with b3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    st.write(f"**Aktuális Brent Ár:** ${curr_p:.2f} | **AI Jóslat:** ${pred_p:.2f}")
    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(5)
    st.rerun()
