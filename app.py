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
# 1. PERMANENS MEMÓRIA ÉS ADATKEZELÉS
# =================================================================
DATA_FILE = "brent_ai_v5_data.json"

def save_state():
    data = {
        "wallet": st.session_state.wallet,
        "history": st.session_state.history,
        "active_trade": st.session_state.active_trade,
        "ai_broker": st.session_state.ai_broker
    }
    with open(DATA_FILE, "w") as f: json.dump(data, f)

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
# 2. UI DESIGN (MODERN & SZIMMETRIKUS)
# =================================================================
st.set_page_config(page_title="BRENT AI - GLOBAL COMMAND", layout="wide")

if 'wallet' not in st.session_state: load_state()

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    .header-box { background: linear-gradient(135deg, #1e2530 0%, #00d4ff 100%); padding: 25px; border-radius: 20px; text-align: center; border: 1px solid #ffffff33; margin-bottom: 20px; }
    .wallet-val { font-size: 42px; font-weight: 900; color: white; text-shadow: 2px 2px 10px rgba(0,0,0,0.5); }
    
    /* CONTROL CENTER - KÖZÉPRE IGAZÍTÁS */
    .control-center { background: #161b22; border: 2px solid #00d4ff; border-radius: 20px; padding: 20px; margin: 20px auto; max-width: 600px; text-align: center; }
    .stToggle { display: flex; justify-content: center; transform: scale(1.4); padding: 10px; }
    
    .news-ticker { background: #1c2128; border-left: 5px solid #f1c40f; padding: 15px; border-radius: 10px; margin-bottom: 20px; font-size: 0.9rem; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 3. ÉLŐ ADAT ÉS STRATÉGIA ($110 SÁV)
# =================================================================
def get_market_data():
    # Brent Futures lekérése
    df = yf.download("BZ=F", period="1d", interval="1m", progress=False)
    if df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df.index = df.index.tz_localize(None)
    return df.dropna()

def get_news_sentiment():
    # Szimulált hírelemző modul a 2026. áprilisi adatok alapján
    return {
        "title": "Hormuzi-szoros: Trump ultimátuma lejár",
        "impact": "BULLISH (Árfelhajtó)",
        "score": 0.85
    }

def trade_logic(action, side, price):
    if action == "OPEN" and not st.session_state.active_trade:
        amt = st.session_state.wallet * 0.75
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': amt, 'time': str(datetime.now())}
        save_state()
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        
        profit = t['amt'] * pnl
        st.session_state.wallet += profit
        st.session_state.history.append({'Idő': datetime.now().strftime("%H:%M:%S"), 'Profit': f"{profit:,.0f} Ft", 'Típus': t['side']})
        st.session_state.active_trade = None
        save_state()

# =================================================================
# 4. DASHBOARD ÉS ROBOT
# =================================================================
data = get_market_data()
news = get_news_sentiment()

if not data.empty:
    curr_p = float(data['Close'].iloc[-1])
    # Mozgóátlagok a trend-lovagláshoz
    sma_trend = data['Close'].rolling(window=20).mean().iloc[-1]
    
    # ROBOT DÖNTÉS: Hírek + Trend
    buy_cond = curr_p > sma_trend and news['score'] > 0.5
    sell_cond = curr_p < sma_trend and news['score'] < 0.3

    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if buy_cond: trade_logic("OPEN", "LONG", curr_p)
            elif sell_cond: trade_logic("OPEN", "SHORT", curr_p)
        else:
            # Csak akkor száll ki, ha a trend határozottan megtörik
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and curr_p < sma_trend * 0.999) or \
               (t['side'] == "SHORT" and curr_p > sma_trend * 1.001):
                trade_logic("CLOSE", None, curr_p)

    # UI: FEJLÉC
    st.markdown(f"""
        <div class="header-box">
            <div style="font-size: 14px; opacity: 0.8;">AKTUÁLIS EGYENLEG</div>
            <div class="wallet-val">{st.session_state.wallet:,.0f} Ft</div>
            <div style="margin-top:10px;"><b>{st.session_state.wallet*0.75:,.0f} Ft</b> aktív tőke</div>
        </div>
    """, unsafe_allow_html=True)

    # UI: HÍREK
    st.markdown(f"""
        <div class="news-ticker">
            <b>📰 ÉLŐ HÍRELEMZÉS:</b> {news['title']}<br>
            <b>Hatás:</b> <span style="color:#00ffcc;">{news['impact']}</span>
        </div>
    """, unsafe_allow_html=True)

    # UI: CONTROL CENTER (SZIMMETRIKUS)
    st.markdown('<div class="control-center">', unsafe_allow_html=True)
    st.markdown(f'<h2 style="color:#00d4ff; margin:0;">BRENT: ${curr_p:.2f}</h2>', unsafe_allow_html=True)
    st.session_state.ai_broker = st.toggle("ROBOT STATUS", value=st.session_state.ai_broker)
    st.markdown('</div>', unsafe_allow_html=True)

    # GRAFIKON
    fig = go.Figure()
    pdf = data.tail(80)
    fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Ár', line=dict(color='white', width=1.5)))
    fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'].rolling(20).mean(), name='Trend', line=dict(color='cyan', width=1, dash='dot')))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        entry_time = pd.to_datetime(t['time'])
        slice_df = pdf[pdf.index >= entry_time]
        t_col = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        if not slice_df.empty:
            fig.add_trace(go.Scatter(x=slice_df.index, y=slice_df['Close'], mode='lines', line=dict(color=t_col, width=5)))
            fig.add_trace(go.Scatter(x=[slice_df.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=15, symbol='star')))

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=10,b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # MANUÁLIS GOMBOK
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🚀 VÉTEL", use_container_width=True): trade_logic("OPEN", "LONG", curr_p)
    with c2: 
        if st.button("📉 ELADÁS", use_container_width=True): trade_logic("OPEN", "SHORT", curr_p)
    with c3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): trade_logic("CLOSE", None, curr_p)

    # ELŐZMÉNYEK
    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(5)
    st.rerun()
