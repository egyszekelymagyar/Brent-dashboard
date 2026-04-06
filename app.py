import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import time
from sklearn.ensemble import RandomForestRegressor

# =================================================================
# 1. KONFIGURÁCIÓ ÉS SZIMMETRIKUS UI DESIGN
# =================================================================
st.set_page_config(page_title="BRENT AI - PERMANENT TRADER", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state: st.session_state.wallet = 1000000.0
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'history' not in st.session_state: st.session_state.history = []
if 'ai_broker' not in st.session_state: st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .wallet-header { background: #161b22; border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 15px; }
    
    /* ROBOT PANEL - FELSŐ RÉSZ */
    .robot-panel { 
        background: #1c2128; 
        border: 3px solid #00d4ff; 
        border-bottom: none;
        padding: 15px; 
        border-radius: 15px 15px 0 0; 
        text-align: center; 
    }
    .robot-title { color: #00d4ff; font-size: 22px; font-weight: 900; display: block; }

    /* SZIMMETRIKUS KAPCSOLÓ KONTÉNER */
    .toggle-wrapper {
        background: #1c2128;
        border: 3px solid #00d4ff;
        border-top: none;
        border-radius: 0 0 15px 15px;
        padding-bottom: 25px;
        display: flex;
        justify-content: center; /* Vízszintes középpont */
        align-items: center;
        margin-bottom: 20px;
    }

    /* STREAMLIT BELÜL KÖZÉPRE KÉNYSZERÍTÉS */
    div[data-testid="stToggle"] {
        margin: 0 auto !important;
        width: fit-content !important;
    }
    
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 1px solid #30363d; padding: 10px; border-radius: 10px; text-align: center; }
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; }
    .signal-box { padding: 20px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 28px; color: #ffffff; font-weight: 900; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS ML MOTOR
# =================================================================
@st.cache_data(ttl=3600)
def load_hist():
    df = yf.download("BZ=F", period="6mo", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    return df.dropna()

@st.cache_data(ttl=2)
def load_live():
    df = yf.download("BZ=F", period="1d", interval="1m", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
    df.index = df.index.tz_localize(None)
    return df.dropna()

def get_ai_prediction(h, l):
    comb = pd.concat([h.tail(100), l.tail(200)])
    comb['Target'] = comb['Close'].shift(-1)
    train = comb.dropna()
    model = RandomForestRegressor(n_estimators=50, random_state=42).fit(
        train[['Open', 'High', 'Low', 'Close']].values, train['Target'].values
    )
    return float(model.predict(l[['Open', 'High', 'Low', 'Close']].iloc[-1:].values)[0])

def manage_trade(action, side, price):
    if action == "OPEN" and not st.session_state.active_trade:
        inv = st.session_state.wallet * 0.75
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': datetime.now()}
    elif action == "CLOSE" and st.session_state.active_trade:
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        st.session_state.wallet += (t['amt'] * pnl)
        st.session_state.history.append({'Idő': datetime.now().strftime("%H:%M:%S"), 'Profit': f"{t['amt']*pnl:,.0f} Ft"})
        st.session_state.active_trade = None

# =================================================================
# 3. DASHBOARD ÉS VEZÉRLÉS
# =================================================================
h, l = load_hist(), load_live()

# KÜSZÖBÉRTÉK ELEMZÉSRE (Sidebar)
with st.sidebar:
    st.header("⚙️ Beállítások")
    threshold = st.slider("Küszöb (Érzékenység)", 0.001, 0.050, 0.010, step=0.001)
    st.info(f"Jelenlegi küszöb: {threshold}")

if l is not None:
    curr_p = float(l['Close'].iloc[-1])
    pred_p = get_ai_prediction(h, l)
    diff = pred_p - curr_p
    
    buy_sig = diff > threshold
    sell_sig = diff < -threshold

    # Automata kereskedés
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if buy_sig: manage_trade("OPEN", "LONG", curr_p)
            elif sell_sig: manage_trade("OPEN", "SHORT", curr_p)
        elif (st.session_state.active_trade['side'] == "LONG" and sell_sig) or \
             (st.session_state.active_trade['side'] == "SHORT" and buy_sig):
            manage_trade("CLOSE", None, curr_p)

    # UI: EGYENLEG
    st.markdown(f'<div class="wallet-header"><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1><small style="color:#f1c40f;">75% TÉT AKTÍV</small></div>', unsafe_allow_html=True)
    
    # UI: ROBOT PANEL ÉS KÖZÉPRE IGAZÍTOTT KAPCSOLÓ
    st.markdown('<div class="robot-panel"><span class="robot-title">🤖 DINAMIKUS ROBOT BRÓKER</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="toggle-wrapper">', unsafe_allow_html=True)
    st.session_state.ai_broker = st.toggle("ROBOT STATUS", value=st.session_state.ai_broker, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    # UI: SZIGNÁL DOBOZ
    color = "#2ecc71" if buy_sig else "#e74c3c" if sell_sig else "#7f8c8d"
    st.markdown(f'<div class="signal-box" style="background-color: {color};"><div class="signal-title">{"VÉTEL! 🚀" if buy_sig else "ELADÁS! 📉" if sell_sig else "ELEMZÉS..."}</div><small>Diff: {diff:.4f} | Küszöb: {threshold}</small></div>', unsafe_allow_html=True)

    # MANUÁLIS GOMBOK
    m1, m2, m3 = st.columns(3)
    with m1: 
        if st.button("🚀 VÉTEL (75%)", use_container_width=True): manage_trade("OPEN", "LONG", curr_p)
    with m2: 
        if st.button("📉 ELADÁS (75%)", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p)
    with m3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # ADAT RÁCS
    st.markdown(f"""<div class="mobile-grid">
        <div class="stat-card"><span>Ár</span><br><span class="stat-value">${curr_p:.2f}</span></div>
        <div class="stat-card"><span>AI Cél</span><br><span class="stat-value">${pred_p:.2f}</span></div>
    </div>""", unsafe_allow_html=True)

    # GRAFIKON
    fig = go.Figure()
    pdf = l.tail(60)
    fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], mode='lines', line=dict(color='white', width=2)))
    
    # AI célvonal vizualizáció
    fig.add_hline(y=pred_p, line_dash="dot", line_color="cyan", opacity=0.4)
    
    if st.session_state.active_trade:
        t = st.session_state.active_trade
        act = pdf[pdf.index >= t['time']]
        scol = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        if not act.empty:
            fig.add_trace(go.Scatter(x=act.index, y=act['Close'], mode='lines', line=dict(color=scol, width=10)))
            fig.add_trace(go.Scatter(x=[act.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=20, symbol='star')))

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=0), showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # NAPLÓ
    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history).tail(5))

    time.sleep(5)
    st.rerun()
