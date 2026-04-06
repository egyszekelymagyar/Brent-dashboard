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

# Session State inicializálása - Ez őrzi meg az egyenleget frissítés után is
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
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: auto auto auto; gap: 10px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 10px; border-radius: 10px; text-align: center; }
    .stat-label { color: #FFFFFF; font-size: 11px; font-weight: 800; text-transform: uppercase; display: block; }
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; display: block; }
    .wallet-header { background: linear-gradient(90deg, #161b22, #232d39); border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 10px; }
    .ai-active { border: 2px solid #00d4ff; box-shadow: 0px 0px 20px rgba(0, 212, 255, 0.6); }
    .signal-box { padding: 20px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 30px !important; color: #ffffff !important; font-weight: 900; margin: 0 !important; }
    
    /* NAGY KAPCSOLÓ STÍLUS */
    .stToggle > div { transform: scale(1.5); padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS ML MOTOR (MINDEN MARADT)
# =================================================================
@st.cache_data(ttl=30)
def load_market_data():
    try:
        df = yf.download("BZ=F", period="2d", interval="1m", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.index = df.index.tz_localize(None)
        return df.dropna()
    except: return None

def get_ai_prediction(df):
    data = df.tail(150).copy()
    data['Target'] = data['Close'].shift(-1)
    data = data.dropna()
    X, y = data[['Open', 'High', 'Low', 'Close']].values, data['Target'].values
    model = RandomForestRegressor(n_estimators=100, random_state=42).fit(X[:-1], y[:-1])
    return float(model.predict(X[-1].reshape(1, -1))[0])

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK
# =================================================================
def manage_trade(action, side, price, risk=75):
    if action == "OPEN":
        if not st.session_state.active_trade:
            investment = st.session_state.wallet * (risk / 100)
            st.session_state.active_trade = {
                'side': side, 'entry': price, 'amt': investment, 'time': datetime.now()
            }
    elif action == "CLOSE":
        if st.session_state.active_trade:
            t = st.session_state.active_trade
            pnl_pct = (price - t['entry']) / t['entry']
            if t['side'] == "SHORT": pnl_pct *= -1
            profit = t['amt'] * pnl_pct
            st.session_state.wallet += profit
            st.session_state.history.append({
                'Idő': datetime.now().strftime("%H:%M"),
                'Típus': t['side'],
                'Profit': f"{profit:+.0f} Ft",
                'Egyenleg': f"{st.session_state.wallet:,.0f} Ft"
            })
            st.session_state.active_trade = None

# =================================================================
# 4. DASHBOARD ÉS LOGIKA
# =================================================================
df = load_market_data()

if df is not None:
    curr_p = df['Close'].iloc[-1]
    pred_p = get_ai_prediction(df)
    diff = pred_p - curr_p
    buy_pct = 100 if pred_p > curr_p else 0
    sell_pct = 100 - buy_pct

    # FEJLÉC
    ai_style = "ai-active" if st.session_state.ai_broker else ""
    st.markdown(f"""<div class="wallet-header {ai_style}"><h3 style="color:#f1c40f;margin:0;">VIRTUÁLIS EGYENLEG</h3><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>""", unsafe_allow_html=True)
    
    # 1. NAGY AI BRÓKER KAPCSOLÓ (JOBBRA BE / BALRA KI)
    col_t1, col_t2, col_t3 = st.columns([1,2,1])
    with col_t2:
        st.session_state.ai_broker = st.toggle(
            f"🤖 ROBOT BRÓKER: {'BE' if st.session_state.ai_broker else 'KI'}", 
            value=st.session_state.ai_broker
        )

    # 2. MANUÁLIS GOMBOK KÖZVETLENÜL ALATTA
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with c2: 
        if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with c3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # IDŐZÓNÁK ÉS 2x3 RÁCS
    t_hu = datetime.now(pytz.timezone('Europe/Budapest')).strftime("%H:%M:%S")
    t_ny = datetime.now(pytz.timezone('America/New_York')).strftime("%H:%M:%S")
    
    st.markdown(f"""<div class="mobile-grid">
        <div class="stat-card"><span class="stat-label">Budapest</span><span class="stat-value">{t_hu}</span></div>
        <div class="stat-card"><span class="stat-label">New York</span><span class="stat-value">{t_ny}</span></div>
        <div class="stat-card"><span class="stat-label">Ár</span><span class="stat-value">${curr_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">Célár</span><span class="stat-value">${pred_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">Vétel</span><span class="stat-value">{buy_pct}%</span></div>
        <div class="stat-card"><span class="stat-label">Eladás</span><span class="stat-value">{sell_pct}%</span></div>
    </div>""", unsafe_allow_html=True)

    # SZIGNÁL PANEL
    status = "VÉTEL! 🚀" if buy_pct > 50 else "ELADÁS! 📉"
    color = "#2ecc71" if buy_pct > 50 else "#e74c3c"
    st.markdown(f"""<div class="signal-box" style="background-color: {color};"><div class="signal-title">{status}</div><div style="font-size: 20px; color: white; font-weight: 800;">Valószínűség: {max(buy_pct, sell_pct)}%</div></div>""", unsafe_allow_html=True)

    # GRAFIKON FIXÁLÁSA (VASTAG GÖRBE + PONTOK)
    fig = go.Figure()
    p_df = df.tail(100)
    
    # Alap árfolyam görbe
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['Close'], name="Ár", line=dict(color='rgba(255,255,255,0.5)', width=2)))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        # Aktív szakasz vastagítása
        mask = p_df.index >= t['time']
        segment = p_df[mask]
        scol = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        
        if not segment.empty:
            fig.add_trace(go.Scatter(x=segment.index, y=segment['Close'], line=dict(color=scol, width=6), name="Aktív Üzlet"))
            # Belépési pont jelölése
            fig.add_trace(go.Scatter(x=[segment.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=15, symbol='star'), name="Belépés"))
        
        fig.add_hline(y=t['entry'], line_dash="dash", line_color="yellow", annotation_text="Beszálló")

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # AI LOGIKA FUTTATÁSA
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if diff > 0.05: manage_trade("OPEN", "LONG", curr_p)
            elif diff < -0.05: manage_trade("OPEN", "SHORT", curr_p)
        else:
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and diff < -0.02) or (t['side'] == "SHORT" and diff > 0.02):
                manage_trade("CLOSE", None, curr_p)

    # AUTO REFRISH
    time.sleep(10)
    st.rerun()
