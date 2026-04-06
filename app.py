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

if 'wallet' not in st.session_state: st.session_state.wallet = 1000000.0
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'history' not in st.session_state: st.session_state.history = []
if 'ai_broker' not in st.session_state: st.session_state.ai_broker = False

# CSS JAVÍTÁS: A KAPCSOLÓT BELEOLVASZTJUK A KERETBE
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .wallet-header { background: #161b22; border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 15px; }
    
    /* EZ A KERET FOGJA ÖSSZE A CÍMET ÉS A KAPCSOLÓT */
    [data-testid="stVerticalBlock"] > div:has(div.robot-box) {
        border: 3px solid #00d4ff;
        border-radius: 15px;
        background-color: #1c2128;
        padding: 20px;
        margin-bottom: 20px;
    }
    .robot-title { color: #00d4ff; font-size: 24px; font-weight: 900; text-align: center; display: block; width: 100%; margin-bottom: 10px; }
    
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 10px; border-radius: 10px; text-align: center; }
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; }
    .signal-box { padding: 20px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 30px !important; color: #ffffff !important; font-weight: 900; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. DINAMIKUS ADAT ÉS ML MOTOR (MÚLTBÓL JÖVŐRE)
# =================================================================
@st.cache_data(ttl=3600)
def load_historical_memory():
    df = yf.download("BZ=F", period="6mo", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    return df.dropna()

@st.cache_data(ttl=2)
def load_market_data():
    df = yf.download("BZ=F", period="1d", interval="1m", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df.index = df.index.tz_localize(None)
    return df.dropna()

def get_dynamic_prediction(hist_df, live_df):
    combined = pd.concat([hist_df.tail(100), live_df.tail(200)])
    combined['Target'] = combined['Close'].shift(-1)
    train = combined.dropna()
    X = train[['Open', 'High', 'Low', 'Close']].values
    y = train['Target'].values
    model = RandomForestRegressor(n_estimators=100, random_state=42).fit(X, y)
    last_val = live_df[['Open', 'High', 'Low', 'Close']].iloc[-1].values.reshape(1, -1)
    return float(model.predict(last_val))

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK (FIX 75% TÉT)
# =================================================================
def manage_trade(action, side, price):
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75 # FIX 75%
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': datetime.now()}
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        profit = t['amt'] * pnl
        st.session_state.wallet += profit
        st.session_state.history.append({'Idő': datetime.now().strftime("%H:%M:%S"), 'Típus': t['side'], 'Profit': f"{profit:,.0f} Ft"})
        st.session_state.active_trade = None

# =================================================================
# 4. DASHBOARD
# =================================================================
hist_df = load_historical_memory()
df = load_market_data()

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    pred_p = get_dynamic_prediction(hist_df, df)
    buy_sig = (pred_p - curr_p) > 0.005
    sell_sig = (pred_p - curr_p) < -0.005

    # Robot Vezérlés
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if buy_sig: manage_trade("OPEN", "LONG", curr_p)
            elif sell_sig: manage_trade("OPEN", "SHORT", curr_p)
        else:
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and sell_sig) or (t['side'] == "SHORT" and buy_sig):
                manage_trade("CLOSE", None, curr_p)

    # 1. EGYENLEG
    st.markdown(f'<div class="wallet-header"><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1><small style="color:#f1c40f;">EGYENLEG (75% TÉT)</small></div>', unsafe_allow_html=True)
    
    # 2. ROBOT PANEL (KAPCSOLÓVAL BELÜL)
    with st.container():
        st.markdown('<div class="robot-box"><span class="robot-title">🤖 DINAMIKUS ROBOT BRÓKER</span></div>', unsafe_allow_html=True)
        st.session_state.ai_broker = st.toggle("ROBOT ÜZEMMÓD AKTIVÁLÁSA", value=st.session_state.ai_broker)

    # 3. SZIGNÁL
    color = "#2ecc71" if buy_sig else "#e74c3c" if sell_sig else "#7f8c8d"
    st.markdown(f'<div class="signal-box" style="background-color: {color};"><div class="signal-title">{"VÉTEL! 🚀" if buy_sig else "ELADÁS! 📉" if sell_sig else "ELEMZÉS..."}</div></div>', unsafe_allow_html=True)

    # 4. GOMBOK
    m1, m2, m3 = st.columns(3)
    with m1: 
        if st.button("🚀 VÉTEL (75%)", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with m2: 
        if st.button("📉 ELADÁS (75%)", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with m3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # 5. RÁCS ÉS GRAFIKON
    st.markdown(f"""<div class="mobile-grid">
        <div class="stat-card"><span>Ár</span><br><span class="stat-value">${curr_p:.2f}</span></div>
        <div class="stat-card"><span>AI Cél</span><br><span class="stat-value">${pred_p:.2f}</span></div>
    </div>""", unsafe_allow_html=True)

    fig = go.Figure()
    plot_df = df.tail(60)
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Close'], mode='lines', line=dict(color='white', width=2)))
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        active_segment = plot_df[plot_df.index >= t['time']]
        scol = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        if not active_segment.empty:
            fig.add_trace(go.Scatter(x=active_segment.index, y=active_segment['Close'], mode='lines', line=dict(color=scol, width=12)))
            fig.add_trace(go.Scatter(x=[active_segment.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=25, symbol='star')))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # 6. NAPLÓ
    if st.session_state.history:
        st.markdown("### 📝 Tranzakciók")
        st.table(pd.DataFrame(st.session_state.history).tail(5))

    time.sleep(5)
    st.rerun()
