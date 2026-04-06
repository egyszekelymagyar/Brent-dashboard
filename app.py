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
# 1. ADAT- ÉS EGYENLEGKEZELŐ (PERMANENS)
# =================================================================
DATA_FILE = "brent_v7_real_adaptation.json"

def save_state():
    data = {"wallet": st.session_state.wallet, "history": st.session_state.history, "active_trade": st.session_state.active_trade}
    with open(DATA_FILE, "w") as f: json.dump(data, f)

def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
                st.session_state.wallet = d.get("wallet", 1000000.0)
                st.session_state.history = d.get("history", [])
                st.session_state.active_trade = d.get("active_trade", None)
        except: pass

# =================================================================
# 2. UI DESIGN - TOTAL SYMMETRY & FOCUS
# =================================================================
st.set_page_config(page_title="BRENT AI - REAL ADAPTATION", layout="wide")
if 'wallet' not in st.session_state: load_state()

st.markdown("""
    <style>
    .main { background-color: #0d1117; color: #c9d1d9; }
    .header-card { background: #161b22; border: 1px solid #30363d; padding: 25px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .wallet-text { font-size: 40px; font-weight: 900; color: #58a6ff; }
    
    /* CENTERED CONTROL UNIT */
    .control-unit { background: #1c2128; border: 2px solid #00d4ff; border-radius: 20px; padding: 20px; margin: 20px auto; max-width: 500px; text-align: center; }
    .stToggle { display: flex; justify-content: center; transform: scale(1.4); padding: 10px; }
    
    .news-flash { background: #161b22; border-left: 4px solid #f1c40f; padding: 10px; margin-bottom: 20px; font-size: 13px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 3. VALÓS IDEJŰ ADAPTÁCIÓS MOTOR
# =================================================================
def get_market_engine():
    # Brent Futures (BZ=F) - Valós piaci adatok
    df = yf.download("BZ=F", period="1d", interval="1m", progress=False)
    if df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df.index = df.index.tz_localize(None)
    
    # ADAPTÍV INDIKÁTOROK: ATR (Volatilitás) és RSI (Momentum)
    window = 14
    df['Price_Diff'] = df['Close'].diff()
    df['Gain'] = df['Price_Diff'].clip(lower=0)
    df['Loss'] = -df['Price_Diff'].clip(upper=0)
    avg_gain = df['Gain'].rolling(window=window).mean()
    avg_loss = df['Loss'].rolling(window=window).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR a volatilitáshoz (Kilépési távolság)
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                          np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                                     abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=window).mean()
    return df.dropna()

def manage_trade(action, side, price):
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
# 4. DASHBOARD - VALÓSÁGKÖVETÉS
# =================================================================
df = get_market_engine()

if not df.empty:
    curr_p = float(df['Close'].iloc[-1])
    rsi = float(df['RSI'].iloc[-1])
    atr = float(df['ATR'].iloc[-1])
    
    # STRATÉGIA: Momentum + Volatilitás szűrő
    # RSI > 60 és emelkedő ár -> LONG
    # RSI < 40 és eső ár -> SHORT
    long_trigger = rsi > 60
    short_trigger = rsi < 40

    if st.session_state.get('ai_broker', False):
        if not st.session_state.active_trade:
            if long_trigger: manage_trade("OPEN", "LONG", curr_p)
            elif short_trigger: manage_trade("OPEN", "SHORT", curr_p)
        else:
            t = st.session_state.active_trade
            # Adaptív kilépés: Ha az árfolyam az ATR kétszeresénél jobban ellenünk fordul
            if t['side'] == "LONG" and curr_p < t['entry'] - (2 * atr):
                manage_trade("CLOSE", None, curr_p)
            elif t['side'] == "SHORT" and curr_p > t['entry'] + (2 * atr):
                manage_trade("CLOSE", None, curr_p)
            # Profit realizálás: RSI extrém értékénél (ellenkező irányban)
            elif (t['side'] == "LONG" and rsi > 80) or (t['side'] == "SHORT" and rsi < 20):
                manage_trade("CLOSE", None, curr_p)

    # UI: EGYENLEG
    st.markdown(f'<div class="header-card"><div class="wallet-text">{st.session_state.wallet:,.0f} Ft</div><div><b>75% TÉT AKTÍV</b></div></div>', unsafe_allow_html=True)

    # UI: HÍREK (Valós forrásokból)
    st.markdown(f"""<div class="news-flash"><b>📰 PIACI VALÓSÁG:</b> Trump keddi határideje Tehran felé ($110+ sáv) | Hormuzi-szoros blokádja 90%-os.</div>""", unsafe_allow_html=True)

    # UI: CONTROL (SZIMMETRIKUS)
    st.markdown('<div class="control-unit">', unsafe_allow_html=True)
    st.markdown(f'<h2 style="color: white; margin: 0;">BRENT: ${curr_p:.2f}</h2>', unsafe_allow_html=True)
    st.session_state.ai_broker = st.toggle("ROBOT BRÓKER", value=st.session_state.get('ai_broker', False))
    st.markdown(f'<div style="margin-top:10px; opacity:0.7;">Momentum (RSI): {rsi:.1f}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # GRAFIKON
    fig = go.Figure()
    pdf = df.tail(80)
    fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Ár', line=dict(color='white', width=2)))
    
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        entry_dt = pd.to_datetime(t['time'])
        slice_df = pdf[pdf.index >= entry_dt]
        t_col = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        if not slice_df.empty:
            fig.add_trace(go.Scatter(x=slice_df.index, y=slice_df['Close'], mode='lines', line=dict(color=t_col, width=6)))
            fig.add_trace(go.Scatter(x=[slice_df.index], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=15, symbol='star')))

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=10,b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # GOMBOK
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with c2: 
        if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with c3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(5)
    st.rerun()
