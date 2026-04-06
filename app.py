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
DATA_FILE = "brent_commander_pro.json"

def save_state():
    data = {"wallet": st.session_state.wallet, "history": st.session_state.history, "active_trade": st.session_state.active_trade, "ai_broker": st.session_state.ai_broker}
    with open(DATA_FILE, "w") as f: json.dump(data, f)

def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
                st.session_state.wallet, st.session_state.history = d.get("wallet", 1000000.0), d.get("history", [])
                st.session_state.active_trade, st.session_state.ai_broker = d.get("active_trade", None), d.get("ai_broker", False)
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
        pnl = ((price - t['entry']) / t['entry']) * (-1 if t['side'] == "SHORT" else 1)
        profit_ft = t['amt'] * pnl
        st.session_state.wallet += (t['amt'] + profit_ft)
        st.session_state.history.append({'Idő': datetime.now().strftime("%H:%M"), 'Irány': t['side'], 'Profit': f"{profit_ft:,.0f} Ft", 'Ár': f"${price:.2f}"})
        st.session_state.active_trade = None
        save_state()
    elif action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.wallet -= inv
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv}
        save_state()

# =================================================================
# 3. PROFI DASHBOARD UI
# =================================================================
st.set_page_config(page_title="BRENT PRO TERMINAL", layout="wide")

# CSS a sötét terminál megjelenéshez
st.markdown("""
    <style>
    .stApp { background-color: #050505; }
    div[data-testid="stMetricValue"] { color: #00ff88 !important; font-size: 32px !important; }
    .stToggle { display: flex; justify-content: center; transform: scale(1.2); margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# Élő árfolyam és indikátorok (A háttérben futó elemzéshez)
data = yf.download("BZ=F", period="1d", interval="1m", progress=False)
if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.droplevel(1)
curr_p = float(data['Close'].iloc[-1]) if not data.empty else 0.0

# FEJLÉC ÉS EGYENLEG
c1, c2 = st.columns(2)
with c1: st.metric("SZÁMLA EGYENLEG", f"{st.session_state.wallet:,.0f} Ft")
with c2: st.metric("BRENT NYERSOLAJ (BZ=F)", f"${curr_p:.2f}")

# ROBOT KAPCSOLÓ (Középen, Mobilon is)
st.session_state.ai_broker = st.toggle("🤖 ROBOT AUTO-PILOT AKTIVÁLÁSA", value=st.session_state.ai_broker)
save_state()

# =================================================================
# 4. ÉLŐ TRADINGVIEW GRAFIKON (VALÓDI REAL-TIME)
# =================================================================
st.write("### 📈 ÉLŐ TŐZSDEI ÁRFOLYAM")
tradingview_html = f"""
<div class="tradingview-widget-container" style="height: 500px;">
  <div id="tradingview_brent"></div>
  <script type="text/javascript" src="https://tradingview.com"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "TVC:UKOIL",
    "interval": "1",
    "timezone": "Europe/Budapest",
    "theme": "dark",
    "style": "1",
    "locale": "hu",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "hide_top_toolbar": false,
    "save_image": false,
    "container_id": "tradingview_brent"
  }});
  </script>
</div>
"""
components.html(tradingview_html, height=500)

# =================================================================
# 5. ROBOT LOGIKA ÉS VEZÉRLÉS
# =================================================================
if st.session_state.ai_broker and not data.empty:
    ema3, ema8 = data['Close'].ewm(span=3).mean().iloc[-1], data['Close'].ewm(span=8).mean().iloc[-1]
    target = "LONG" if ema3 > ema8 else "SHORT"
    if not st.session_state.active_trade: manage_trade("OPEN", target, curr_p)
    elif st.session_state.active_trade['side'] != target:
        manage_trade("CLOSE", None, curr_p)
        manage_trade("OPEN", target, curr_p)

# MANUÁLIS GOMBOK
col1, col2, col3 = st.columns(3)
with col1: st.button("🚀 VÉTEL (75%)", on_click=manage_trade, args=("OPEN", "LONG", curr_p), use_container_width=True)
with col2: st.button("📉 ELADÁS (75%)", on_click=manage_trade, args=("OPEN", "SHORT", curr_p), use_container_width=True)
with col3: st.button("❌ KÉZI ZÁRÁS", on_click=manage_trade, args=("CLOSE", None, curr_p), use_container_width=True)

# NAPLÓ
if st.session_state.history:
    st.table(pd.DataFrame(st.session_state.history).tail(3))

time.sleep(2)
st.rerun()
