import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import time
import json
import os

# =================================================================
# 1. ADATBÁZIS ÉS MOTOR (75% TÉT)
# =================================================================
DATA_FILE = "brent_smart_monitor.json"

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
# 2. KERESKEDÉSI FUNKCIÓK
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
# 3. OKOS ÁRKÖVETŐ UI (MODERN & TISZTA)
# =================================================================
st.set_page_config(page_title="BRENT SMART TRACKER", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #050505; color: white; }
    .price-box { background: #111; border-radius: 15px; padding: 25px; text-align: center; border: 1px solid #333; margin-bottom: 10px; }
    .momentum-bar { height: 10px; border-radius: 5px; background: #333; margin: 10px 0; overflow: hidden; }
    .momentum-fill { height: 100%; transition: width 0.5s ease-in-out; }
    .stToggle { display: flex; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

# Élő adatlekérés
data = yf.download("BZ=F", period="1d", interval="1m", progress=False)
if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.droplevel(1)

if not data.empty:
    curr_p = float(data['Close'].iloc[-1])
    prev_p = float(data['Close'].iloc[-2])
    change = curr_p - prev_p
    
    # OKOS INDIKÁTOR: Momentum mérés (Az utolsó 5 perc ereje)
    ema5 = data['Close'].ewm(span=5).mean().iloc[-1]
    momentum_pct = ((curr_p - ema5) / ema5) * 1000 # Erősített skála a látványért
    
    # UI: Fő Árkijelző
    st.markdown(f"""
        <div class="price-box">
            <small style="color: #888; text-transform: uppercase; letter-spacing: 2px;">Brent Aktuális Árfolyam</small>
            <h1 style="font-size: 64px; margin: 10px 0; color: {'#00ff88' if change >= 0 else '#ff4b4b'};">
                ${curr_p:.2f}
            </h1>
            <p style="font-size: 20px; color: {'#00ff88' if change >= 0 else '#ff4b4b'};">
                {'▲' if change >= 0 else '▼'} {abs(change):.2f} ({(change/prev_p)*100:+.3f}%)
            </p>
        </div>
    """, unsafe_allow_html=True)

    # UI: Momentum Monitor (Vevők vs Eladók)
    buy_power = min(max(50 + (momentum_pct * 10), 0), 100)
    sell_power = 100 - buy_power
    
    col_a, col_b = st.columns(2)
    with col_a: st.write(f"🟢 VEVŐK: {buy_power:.1f}%")
    with col_b: st.write(f"🔴 ELADÓK: {sell_power:.1f}%", )
    st.markdown(f"""
        <div class="momentum-bar">
            <div class="momentum-fill" style="width: {buy_power}%; background: #00ff88;"></div>
        </div>
    """, unsafe_allow_html=True)

    # KAPCSOLÓ KÖZÉPEN
    st.session_state.ai_broker = st.toggle("🤖 OKOS ROBOT AKTIVÁLÁSA", value=st.session_state.ai_broker)
    save_state()

    # ROBOT LOGIKA
    if st.session_state.ai_broker:
        target = "LONG" if buy_power > 55 else ("SHORT" if sell_power > 55 else None)
        if target:
            if not st.session_state.active_trade:
                manage_trade("OPEN", target, curr_p)
            elif st.session_state.active_trade['side'] != target:
                manage_trade("CLOSE", None, curr_p)

    # ÜGYFÉLPANEL
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("SZÁMLA", f"{st.session_state.wallet:,.0f} Ft")
    with c2: 
        if st.session_state.active_trade:
            t = st.session_state.active_trade
            pnl = ((curr_p - t['entry']) / t['entry']) * (1 if t['side'] == "LONG" else -1)
            st.metric("NYITOTT POZÍCIÓ", f"{pnl*100:+.2f}%", delta=t['side'])
        else: st.write("Nincs aktív trade")
    with c3:
        if st.button("❌ AZONNALI ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(2)
    st.rerun()
