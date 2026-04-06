import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz
import time
from sklearn.ensemble import RandomForestRegressor

# =================================================================
# 1. KONFIGURÁCIÓ ÉS ÁLLANDÓ MEMÓRIA
# =================================================================
st.set_page_config(page_title="BRENT AI - PERMANENT TRADER", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state:
    st.session_state.wallet = 1000000.0
if 'active_trade' not in st.session_state:
    st.session_state.active_trade = None
if 'history' not in st.session_state:
    st.session_state.history = []
if 'ai_broker' not in st.session_state:
    st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 1px solid #30363d; padding: 10px; border-radius: 10px; text-align: center; }
    .stat-label { color: #8b949e; font-size: 11px; font-weight: 800; text-transform: uppercase; display: block; }
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; display: block; }
    .wallet-header { background: #161b22; border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 10px; }
    .robot-header { background: #1c2128; border: 2px solid #00d4ff; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 10px; }
    .signal-box { padding: 20px; border-radius: 15px; text-align: center; border: 2px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 24px; color: #ffffff; font-weight: 900; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS ML MOTOR
# =================================================================
@st.cache_data(ttl=2)
def load_market_data():
    try:
        df = yf.download("BZ=F", period="1d", interval="1m", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.index = df.index.tz_localize(None)
        return df.dropna()
    except: return None

def get_ai_prediction(df):
    if len(df) < 20: return float(df['Close'].iloc[-1])
    data = df.tail(100).copy()
    data['Target'] = data['Close'].shift(-1)
    train = data.dropna()
    X = train[['Open', 'High', 'Low', 'Close']].values
    y = train['Target'].values
    model = RandomForestRegressor(n_estimators=30, random_state=42).fit(X, y)
    last_features = df[['Open', 'High', 'Low', 'Close']].iloc[-1].values.reshape(1, -1)
    return float(model.predict(last_features)[0])

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK
# =================================================================
def manage_trade(action, side, price, risk_pct=50):
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * (risk_pct / 100)
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': datetime.now()}
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl_pct = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl_pct *= -1
        profit = t['amt'] * pnl_pct
        st.session_state.wallet += profit
        st.session_state.history.append({
            'Idő': datetime.now().strftime("%H:%M"),
            'Típus': t['side'],
            'Profit': f"{profit:,.0f} Ft"
        })
        st.session_state.active_trade = None

# =================================================================
# 4. DASHBOARD ÉS VEZÉRLÉS
# =================================================================
df = load_market_data()

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    pred_p = get_ai_prediction(df)
    
    # Szignál logika
    diff = pred_p - curr_p
    buy_signal = diff > 0.01 
    sell_signal = diff < -0.01

    # Automata Bróker döntés
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if buy_signal: manage_trade("OPEN", "LONG", curr_p)
            elif sell_signal: manage_trade("OPEN", "SHORT", curr_p)
        else:
            # Zárás, ha megfordul a trend
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and sell_signal) or (t['side'] == "SHORT" and buy_signal):
                manage_trade("CLOSE", None, curr_p)

    # --- UI MEGJELENÍTÉS ---
    st.markdown(f'<div class="wallet-header"><span style="color:#f1c40f">EGYENLEG:</span> <span style="color:white">{st.session_state.wallet:,.0f} Ft</span></div>', unsafe_allow_html=True)
    
    col_ai, col_sig = st.columns([1, 2])
    with col_ai:
        st.session_state.ai_broker = st.toggle("🤖 ROBOT AUTO-TRADER", value=st.session_state.ai_broker)
    with col_sig:
        color = "#2ecc71" if buy_signal else "#e74c3c" if sell_signal else "#7f8c8d"
        txt = "VÉTEL 🚀" if buy_signal else "ELADÁS 📉" if sell_signal else "VÁRAKOZÁS ⏳"
        st.markdown(f'<div class="signal-box" style="background-color: {color};"><div class="signal-title">{txt}</div></div>', unsafe_allow_html=True)

    # Manuális gombok
    m1, m2, m3 = st.columns(3)
    with m1: 
        if st.button("🚀 LONG", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with m2: 
        if st.button("📉 SHORT", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with m3: 
        if st.button("❌ CLOSE", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # Statisztikák
    t_hu = datetime.now(pytz.timezone('Europe/Budapest')).strftime("%H:%M:%S")
    st.markdown(f"""<div class="mobile-grid">
        <div class="stat-card"><span class="stat-label">Idő (HU)</span><span class="stat-value">{t_hu}</span></div>
        <div class="stat-card"><span class="stat-label">Brent Ár</span><span class="stat-value">${curr_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">AI Cél</span><span class="stat-value">${pred_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">Státusz</span><span class="stat-value">{'POZÍCIÓBAN' if st.session_state.active_trade else 'ÜRES'}</span></div>
    </div>""", unsafe_allow_html=True)

    # Grafikon
    fig = go.Figure()
    plot_df = df.tail(50)
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Close'], name="Brent", line=dict(color='cyan', width=2)))
    
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        fig.add_hline(y=t['entry'], line_dash="dot", line_color="yellow", annotation_text="BELÉPÉS")

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Napló
    if st.session_state.history:
        with st.expander("Tranzakciós Napló"):
            st.table(pd.DataFrame(st.session_state.history).tail(5))

    # AUTO-REFRESH (5 másodperc)
    time.sleep(5)
    st.rerun()
else:
    st.error("Nincs piaci adat. Ellenőrizd az internetet vagy a Yahoo API-t!")
