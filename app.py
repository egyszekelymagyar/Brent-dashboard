import streamlit as st
import pandas as pd
import yfinance as yf
import streamlit.components.v1 as components
from datetime import datetime
import time
import json
import os

# =================================================================
# 1. VERZIÓ ELLENŐRZÉS ÉS ÁLLAPOTKEZELÉS
# =================================================================
DATA_FILE = "brent_trend_radar_final.json"
VERSION = "TREND-RADAR V5.1 (FIXED)"

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
        except Exception: pass

if 'wallet' not in st.session_state:
    st.session_state.wallet, st.session_state.history = 1000000.0, []
    st.session_state.active_trade, st.session_state.ai_broker = None, False
    load_state()

# =================================================================
# 2. ADATLEKÉRÉS (HIBAJAVÍTOTT)
# =================================================================
def get_live_data():
    try:
        # A multi_level_index=False megakadályozza a MultiIndex lefagyást
        df = yf.download("BZ=F", period="1d", interval="1m", progress=False, multi_level_index=False)
        if df.empty:
            return None
        # Az oszlopnevek tisztítása (néha kisbetű/nagybetű eltérés lehet)
        df.columns = [str(col).capitalize() for col in df.columns]
        return df
    except Exception as e:
        st.error(f"Adatlekérési hiba: {e}")
        return None

# =================================================================
# 3. KERESKEDÉSI MOTOR (75% TÉT)
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
            'Eredmény': f"{pnl_pct*100:+.2f}%"
        })
        st.session_state.active_trade = None
        save_state()
    elif action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.wallet -= inv
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv}
        save_state()

# =================================================================
# 4. UI ÉS VIZUÁLIS ELEMEK
# =================================================================
st.set_page_config(page_title="BRENT TREND RADAR V5.1", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #050505; color: white; }
    .warning-banner { background: #ffaa00; color: black; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin: 10px 0; animation: blink 1.5s infinite; }
    @keyframes blink { 50% { opacity: 0.5; } }
    </style>
    """, unsafe_allow_html=True)

st.caption(f"🚀 Rendszer állapot: {VERSION}")

# Adatok betöltése
data = get_live_data()

if data is not None:
    curr_p = float(data['Close'].iloc[-1])
    ema_fast = data['Close'].ewm(span=12).mean().iloc[-1]
    ema_slow = data['Close'].ewm(span=26).mean().iloc[-1]
    trend_side = "LONG" if ema_fast > ema_slow else "SHORT"
    
    gap = abs(ema_fast - ema_slow)
    is_warning = gap < (curr_p * 0.00018) # Viharjelző küszöb

    # FELSŐ PANEL
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("SZÁMLA", f"{st.session_state.wallet:,.0f} Ft")
    with c2: 
        if st.session_state.active_trade:
            t = st.session_state.active_trade
            pnl = ((curr_p - t['entry']) / t['entry']) * (1 if t['side'] == "LONG" else -1)
            st.metric("ÉLŐ PNL", f"{pnl*100:+.2f}%", delta=t['side'])
        else: st.info("Várakozás trendre...")
    with c3: st.metric("BRENT ÁR", f"${curr_p:.2f}")

    if st.session_state.active_trade and is_warning:
        st.markdown('<div class="warning-banner">⚠️ TREND GYENGÜLÉS! ROBOT ZÁRÁSRA KÉSZÜL!</div>', unsafe_allow_html=True)

    # KAPCSOLÓ
    st.session_state.ai_broker = st.toggle("🤖 TREND-RADAR AKTIVÁLÁSA", value=st.session_state.ai_broker)
    save_state()

    # ROBOT LOGIKA
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            manage_trade("OPEN", trend_side, curr_p)
        elif st.session_state.active_trade['side'] != trend_side:
            manage_trade("CLOSE", None, curr_p)

    # ÉLŐ GRAFIKON (TradingView)
    tradingview_html = """
    <div style="height: 450px;"><div id="tv_chart"></div>
    <script type="text/javascript" src="https://tradingview.com"></script>
    <script type="text/javascript">
    new TradingView.widget({"autosize": true, "symbol": "TVC:UKOIL", "interval": "1", "theme": "dark", "container_id": "tv_chart"});
    </script></div>
    """
    components.html(tradingview_html, height=450)

    # VEZÉRLÉS
    col1, col2, col3 = st.columns(3)
    with col1: st.button("🚀 KÉZI VÉTEL", on_click=manage_trade, args=("OPEN", "LONG", curr_p), use_container_width=True)
    with col2: st.button("📉 KÉZI ELADÁS", on_click=manage_trade, args=("OPEN", "SHORT", curr_p), use_container_width=True)
    with col3: st.button("❌ ZÁRÁS", on_click=manage_trade, args=("CLOSE", None, curr_p), use_container_width=True)

    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(3))
else:
    st.warning("⚠️ Adatok betöltése... Frissítés folyamatban.")

time.sleep(3)
st.rerun()
