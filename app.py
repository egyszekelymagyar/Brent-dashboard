import streamlit as st
import pandas as pd
import yfinance as yf
import streamlit.components.v1 as components
from datetime import datetime
import time
import json
import os

# =================================================================
# 1. ADATBÁZIS ÉS ÁLLAPOTKEZELÉS
# =================================================================
DATA_FILE = "brent_commander_v5.json"

def save_state():
    data = {"wallet": st.session_state.wallet, "history": st.session_state.history, "active_trade": st.session_state.active_trade, "ai_broker": st.session_state.ai_broker}
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

if 'wallet' not in st.session_state:
    st.session_state.wallet, st.session_state.history = 1000000.0, []
    st.session_state.active_trade, st.session_state.ai_broker = None, False
    load_state()

# =================================================================
# 2. KERESKEDÉSI MOTOR (75% TÉT)
# =================================================================
def manage_trade(action, side, price):
    if action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl_pct = ((price - t['entry']) / t['entry']) * (1 if t['side'] == "LONG" else -1)
        profit_ft = t['amt'] * pnl_pct
        st.session_state.wallet += (t['amt'] + profit_ft)
        st.session_state.history.append({
            'Idő': datetime.now().strftime("%H:%M:%S"),
            'Irány': t['side'],
            'Profit': f"{profit_ft:,.0f} Ft",
            'Százalék': f"{pnl_pct*100:+.2f}%"
        })
        st.session_state.active_trade = None
        save_state()
    elif action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.wallet -= inv
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv}
        save_state()

# =================================================================
# 3. DASHBOARD UI ÉS FIGYELMEZTETÉSEK
# =================================================================
st.set_page_config(page_title="BRENT COMMANDER V5 - RADAR", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #050505; }
    .warning-box { background: #ffaa00; color: black; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; animation: blinker 1s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.3; } }
    .stToggle { display: flex; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

# Adatletöltés elemzéshez
data = yf.download("BZ=F", period="1d", interval="1m", progress=False)
if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.droplevel(1)
curr_p = float(data['Close'].iloc[-1]) if not data.empty else 0.0

# --- TREND ELEMZÉS ---
if not data.empty:
    ema3 = data['Close'].ewm(span=3).mean()
    ema8 = data['Close'].ewm(span=8).mean()
    diff = abs(ema3.iloc[-1] - ema8.iloc[-1])
    trend_side = "LONG" if ema3.iloc[-1] > ema8.iloc[-1] else "SHORT"
    
    # Kritikus közelség (zárási figyelmeztetés) küszöbe
    is_warning = diff < (curr_p * 0.00015) # Ha az átlagok 0.015%-ra megközelítik egymást

# FEJLÉC
c1, c2, c3 = st.columns(3)
with c1: st.metric("SZÁMLA", f"{st.session_state.wallet:,.0f} Ft")
with c2: 
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = ((curr_p - t['entry']) / t['entry']) * (1 if t['side'] == "LONG" else -1)
        st.metric("ÉLŐ PNL", f"{pnl*100:+.2f}%", delta=f"{t['side']}")
    else: st.write("💤 VÁRAKOZÁS")
with c3: st.metric("BRENT", f"${curr_p:.2f}")

# --- FIGYELMEZTETÉS KIJELZÉSE ---
if st.session_state.active_trade and is_warning:
    st.markdown('<div class="warning-box">⚠️ FIGYELEM: TRENDFORDULÓ KÖZEL! A ROBOT ZÁRÁSRA KÉSZÜL!</div>', unsafe_allow_html=True)

# KAPCSOLÓ
st.session_state.ai_broker = st.toggle("🤖 RADAR VEZÉRELT AUTO-PILOT", value=st.session_state.ai_broker)

# GRAFIKON
tradingview_html = """
<div class="tradingview-widget-container" style="height: 400px;">
  <div id="tv_chart"></div>
  <script type="text/javascript" src="https://tradingview.com"></script>
  <script type="text/javascript">
  new TradingView.widget({"autosize": true, "symbol": "TVC:UKOIL", "interval": "1", "theme": "dark", "container_id": "tv_chart"});
  </script>
</div>
"""
components.html(tradingview_html, height=400)

# =================================================================
# 4. ROBOT LOGIKA
# =================================================================
if st.session_state.ai_broker and not data.empty:
    if not st.session_state.active_trade:
        manage_trade("OPEN", trend_side, curr_p)
    else:
        # Ha megvan az ellentétes trend, vagy a trend elfogyott (zárás)
        if st.session_state.active_trade['side'] != trend_side:
            manage_trade("CLOSE", None, curr_p)

# GOMBOK
col1, col2, col3 = st.columns(3)
with col1: st.button("🚀 VÉTEL", on_click=manage_trade, args=("OPEN", "LONG", curr_p), use_container_width=True)
with col2: st.button("📉 ELADÁS", on_click=manage_trade, args=("OPEN", "SHORT", curr_p), use_container_width=True)
with col3: st.button("❌ ZÁRÁS", on_click=manage_trade, args=("CLOSE", None, curr_p), use_container_width=True)

if st.session_state.history:
    st.table(pd.DataFrame(st.session_state.history).tail(3))

time.sleep(2)
st.rerun()
