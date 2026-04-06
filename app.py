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
# 1. ÁLLANDÓ MEMÓRIA (MENTÉS ÉS BETÖLTÉS)
# =================================================================
DATA_FILE = "trading_data.json"

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
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
                st.session_state.wallet = data.get("wallet", 1000000.0)
                st.session_state.history = data.get("history", [])
                st.session_state.active_trade = data.get("active_trade", None)
            except: pass

# =================================================================
# 2. KONFIGURÁCIÓ ÉS DESIGN (SZIMMETRIKUS UI)
# =================================================================
st.set_page_config(page_title="BRENT AI - AGGRESSIVE TRADER", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state: 
    st.session_state.wallet = 1000000.0
    load_data()
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'history' not in st.session_state: st.session_state.history = []
if 'ai_broker' not in st.session_state: st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .wallet-header { background: #161b22; border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 15px; }
    .robot-panel { background: #1c2128; border: 3px solid #00d4ff; padding: 10px; border-radius: 15px 15px 0 0; text-align: center; margin-top:10px; }
    .robot-title { color: #00d4ff; font-size: 20px; font-weight: 900; }
    .signal-box { padding: 15px; border-radius: 15px; text-align: center; border: 3px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 24px; color: #ffffff; font-weight: 900; margin: 0; }
    
    /* Teljes szimmetria a kapcsolónak */
    .stToggle { display: flex; justify-content: center; transform: scale(1.2); padding: 10px; }
    div[data-testid="stColumn"] { display: flex; justify-content: center; align-items: center; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 3. ADAT ÉS AGGRESSZÍV ML MOTOR
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
        # Rövidebb ablak a gyorsabb reakcióért
        comb = pd.concat([h.tail(30), l.tail(60)])
        comb['Target'] = comb['Close'].shift(-1)
        train = comb.dropna()
        model = RandomForestRegressor(n_estimators=20, random_state=42).fit(
            train[['Open', 'High', 'Low', 'Close']].values, train['Target'].values
        )
        return float(model.predict(l[['Open', 'High', 'Low', 'Close']].iloc[-1:].values))
    except: return float(l['Close'].iloc[-1])

def manage_trade(action, side, price):
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': datetime.now().isoformat()}
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
# 4. DASHBOARD - FOLYAMATOS ÜZEMMÓD
# =================================================================
h, l = load_hist(), load_live()
# AGGRESSZÍV KÜSZÖB (Sok tranzakcióhoz)
threshold = 0.002 

if l is not None and not l.empty:
    curr_p = float(l['Close'].iloc[-1])
    pred_p = get_ai_prediction(h, l)
    diff = pred_p - curr_p
    
    buy_sig = diff > threshold
    sell_sig = diff < -threshold

    # BEVÁLLALÓS ROBOT LOGIKA
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if buy_sig: manage_trade("OPEN", "LONG", curr_p)
            elif sell_sig: manage_trade("OPEN", "SHORT", curr_p)
        else:
            # Gyors irányváltás követése
            current_side = st.session_state.active_trade['side']
            if (current_side == "LONG" and sell_sig) or (current_side == "SHORT" and buy_sig):
                manage_trade("CLOSE", None, curr_p)

    # UI: EGYENLEG
    st.markdown(f'<div class="wallet-header"><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1><small style="color:#00ffcc;">FOLYAMATOS MENTÉS AKTÍV</small></div>', unsafe_allow_html=True)
    
    # UI: SZIMMETRIKUS ROBOT PANEL
    st.markdown('<div class="robot-panel"><span class="robot-title">🤖 AGGRESSZÍV ROBOT BRÓKER</span></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.session_state.ai_broker = st.toggle("ROBOT STATUS", value=st.session_state.ai_broker, label_visibility="collapsed")

    # UI: SZIGNÁL
    color = "#2ecc71" if buy_sig else "#e74c3c" if sell_sig else "#7f8c8d"
    st.markdown(f'<div class="signal-box" style="background-color: {color};"><div class="signal-title">{"VÉTEL! 🚀" if buy_sig else "ELADÁS! 📉" if sell_sig else "KERESÉS..."}</div></div>', unsafe_allow_html=True)

    # MANUÁLIS GOMBOK (Ha te is bele akarsz nyúlni)
    m1, m2, m3 = st.columns(3)
    with m1: 
        if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with m2: 
        if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with m3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # GRAFIKON - KÖVETŐ VONALLAL
    fig = go.Figure()
    pdf = l.tail(60).copy()
    fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], mode='lines', line=dict(color='white', width=1), opacity=0.4))
    
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        entry_time = pd.to_datetime(t['time'])
        trade_data = pdf[pdf.index >= entry_time]
        trade_color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        
        if not trade_data.empty:
            # Követő vonal a belépéstől az aktuális pontig
            fig.add_trace(go.Scatter(x=trade_data.index, y=trade_data['Close'], mode='lines+markers', line=dict(color=trade_color, width=6)))
            # Belépési pont jelölése
            fig.add_trace(go.Scatter(x=[trade_data.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=18, symbol='star')))

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=10,b=0), showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # INFÓK ÉS NAPLÓ
    st.markdown(f"**Ár:** ${curr_p:.2f} | **AI Cél:** ${pred_p:.2f} | **Különbség:** {diff:.4f}")
    if st.session_state.history:
        st.markdown("### 📝 Utolsó Tranzakciók")
        st.table(pd.DataFrame(st.session_state.history).tail(5))

    time.sleep(5)
    st.rerun()
