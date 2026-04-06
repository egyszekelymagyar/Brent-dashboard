import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz
import time
import feedparser
from sklearn.ensemble import RandomForestRegressor

# =================================================================
# 1. KONFIGURÁCIÓ ÉS MEMÓRIA
# =================================================================
st.set_page_config(page_title="BRENT AI - ULTIMATE HYBRID", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state: st.session_state.wallet = 1000000.0
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'history' not in st.session_state: st.session_state.history = []
if 'ai_broker' not in st.session_state: st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 12px; border-radius: 10px; text-align: center; }
    .stat-label { color: #FFFFFF; font-size: 12px; font-weight: 800; text-transform: uppercase; display: block; }
    .stat-value { color: #00ffcc; font-size: 20px; font-weight: 900; display: block; }
    .wallet-header { background: linear-gradient(90deg, #161b22, #232d39); border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .ai-glow { border: 2px solid #00d4ff; box-shadow: 0px 0px 15px rgba(0, 212, 255, 0.5); }
    .learning-log { background-color: #161b22; border: 1px solid #f1c40f; padding: 10px; border-radius: 8px; color: #f1c40f; font-family: monospace; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS ML MOTOR (HIBAVÉDELEMMEL)
# =================================================================
@st.cache_data(ttl=30)
def load_all_data():
    try:
        # Próbáljunk meg adatot kérni (BZ=F a Brent ticker)
        df_m = yf.download("BZ=F", period="2d", interval="1m", progress=False)
        df_h = yf.download("BZ=F", period="5d", interval="1h", progress=False)
        
        for d in [df_m, df_h]:
            if d.empty: return None, None
            if isinstance(d.columns, pd.MultiIndex): 
                d.columns = d.columns.get_level_values(0)
        return df_m.dropna(), df_h.dropna()
    except:
        return None, None

def get_ml_pred(df):
    if len(df) < 50: return df['Close'].iloc[-1]
    data = df.tail(150).copy()
    data['Target'] = data['Close'].shift(-1)
    data = data.dropna()
    X, y = data[['Open', 'High', 'Low', 'Close']].values, data['Target'].values
    model = RandomForestRegressor(n_estimators=50, random_state=42).fit(X[:-1], y[:-1])
    return model.predict(X[-1].reshape(1, -1))[0]

@st.cache_data(ttl=300)
def get_news_sent():
    try:
        feed = feedparser.parse("https://google.com")
        score = 0.5
        headlines = []
        for entry in feed.entries[:3]:
            txt = entry.title.lower()
            headlines.append(entry.title)
            if any(w in txt for w in ['rise', 'cut', 'shortage']): score += 0.1
            if any(w in txt for w in ['drop', 'glut', 'down']): score -= 0.1
        return score, headlines
    except:
        return 0.5, ["Hírek nem elérhetőek"]

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK
# =================================================================
def manage_trade(action, side, price, risk=75):
    if action == "OPEN":
        investment = st.session_state.wallet * (risk / 100)
        st.session_state.active_trade = {
            'side': side, 'entry_price': price, 'amount_huf': investment,
            'time': datetime.now(pytz.timezone('Europe/Budapest'))
        }
    elif action == "CLOSE":
        t = st.session_state.active_trade
        pnl = (price - t['entry_price']) / t['entry_price']
        if t['side'] == "SHORT": pnl *= -1
        profit = t['amount_huf'] * pnl
        st.session_state.wallet += profit
        st.session_state.history.append({
            'Idő': datetime.now().strftime("%H:%M"), 
            'Típus': t['side'], 
            'Profit': f"{profit:+.0f} Ft"
        })
        st.session_state.active_trade = None

# =================================================================
# 4. FŐ PROGRAMFUTÁS
# =================================================================
df_m, df_h = load_all_data()

# CSAK AKKOR FUTUNK, HA VAN ADAT
if df_m is not None and not df_m.empty:
    curr_p = df_m['Close'].iloc[-1]
    pred_p = get_ml_pred(df_m)
    sent_val, news = get_news_sent()
    diff = pred_p - curr_p

    # Sidebar
    with st.sidebar:
        st.header("🤖 Robot Kontroll")
        risk_val = st.slider("Kockázat (% tőke)", 0, 100, 75)
        threshold = st.slider("AI Küszöb (USD)", 0.05, 0.50, 0.10)
        st.session_state.ai_broker = st.toggle("AI BRÓKER AKTÍV", value=st.session_state.ai_broker)
        if st.button("PORTFÓLIÓ RESET"):
            st.session_state.wallet = 1000000.0
            st.session_state.history = []
            st.rerun()

    # Wallet & Rács
    glow = "ai-glow" if st.session_state.ai_broker else ""
    st.markdown(f"""<div class="wallet-header {glow}"><h3 style="color:#f1c40f;margin:0;">VIRTUÁLIS TŐKE</h3><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>""", unsafe_allow_html=True)
    
    t_hu = datetime.now(pytz.timezone('Europe/Budapest')).strftime("%H:%M:%S")
    st.markdown(f"""
        <div class="mobile-grid">
            <div class="stat-card"><span class="stat-label">Budapest</span><span class="stat-value">{t_hu}</span></div>
            <div class="stat-card"><span class="stat-label">Brent Ár</span><span class="stat-value">${curr_p:.2f}</span></div>
            <div class="stat-card"><span class="stat-label">ML Jóslat</span><span class="stat-value">${pred_p:.2f}</span></div>
            <div class="stat-card"><span class="stat-label">Szentiment</span><span class="stat-value">{sent_val:.2f}</span></div>
        </div>
    """, unsafe_allow_html=True)

    # Bróker Logika
    if st.session_state.ai_broker:
        if not st.session_state.active_trade:
            if diff > threshold: manage_trade("OPEN", "LONG", curr_p, risk_val)
            elif diff < -threshold: manage_trade("OPEN", "SHORT", curr_p, risk_val)
        else:
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and diff < -0.02) or (t['side'] == "SHORT" and diff > 0.02):
                manage_trade("CLOSE", None, curr_p)
    else:
        c1, c2, c3 = st.columns(3)
        with c1: 
            if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p, risk_val)
        with c2: 
            if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p, risk_val)
        with c3: 
            if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # Grafikon
    fig = go.Figure()
    p_df = df_m.tail(60)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['Close'], name="Ár", line=dict(color='white', width=1.5)))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        col = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        mask = p_df.index >= t['time'].replace(tzinfo=None)
        segment = p_df[mask]
        if not segment.empty:
            fig.add_trace(go.Scatter(x=segment.index, y=segment['Close'], line=dict(color=col, width=6), name="ÜZLET"))
        fig.add_hline(y=t['entry_price'], line_dash="dash", line_color="yellow")

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)

    # Napló
    st.subheader("🧠 Tanulási Napló")
    st.markdown(f'<div class="learning-log">ML: Elmozdulás: {diff:+.4f} USD<br>Kockázat: {risk_val}%<br>Állapot: {"Robot" if st.session_state.ai_broker else "Manuális"}</div>', unsafe_allow_html=True)
    
    if st.session_state.history: 
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(30)
    st.rerun()

else:
    st.warning("⏳ Várakozás élő piaci adatokra (A tőzsde jelenleg zárva lehet)...")
    time.sleep(60)
    st.rerun()
