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
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; display: block; }
    .wallet-header { background: linear-gradient(90deg, #161b22, #232d39); border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .ai-glow { border: 2px solid #00d4ff; box-shadow: 0px 0px 15px rgba(0, 212, 255, 0.5); }
    .signal-box { padding: 30px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 20px; }
    .signal-title { font-size: 40px !important; color: #ffffff !important; font-weight: 900; text-shadow: 2px 2px 4px #000; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADATKEZELÉS (HIBAVÉDÉLEMMEL)
# =================================================================
@st.cache_data(ttl=30)
def load_market_data():
    try:
        df = yf.download("BZ=F", period="5d", interval="5m", progress=False)
        if df.empty or len(df) < 20: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except: return None

def get_ai_prediction(df):
    data = df.tail(150).copy()
    data['Target'] = data['Close'].shift(-1)
    data = data.dropna()
    X, y = data[['Open', 'High', 'Low', 'Close']].values, data['Target'].values
    model = RandomForestRegressor(n_estimators=50, random_state=42).fit(X[:-1], y[:-1])
    return model.predict(X[-1].reshape(1, -1))[0]

@st.cache_data(ttl=300)
def get_sentiment():
    try:
        feed = feedparser.parse("https://google.com")
        score = 0.5
        for entry in feed.entries[:3]:
            txt = entry.title.lower()
            if any(w in txt for w in ['rise', 'cut', 'shortage', 'demand']): score += 0.1
            if any(w in txt for w in ['drop', 'glut', 'surplus', 'down']): score -= 0.1
        return min(max(score, 0.1), 0.9), [e.title for e in feed.entries[:3]]
    except: return 0.5, ["Hírek nem elérhetőek"]

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK
# =================================================================
def manage_trade(action, side, price, risk=75):
    if action == "OPEN":
        inv = st.session_state.wallet * (risk / 100)
        st.session_state.active_trade = {'side': side, 'entry': price, 'amt': inv, 'time': datetime.now(pytz.timezone('Europe/Budapest'))}
    elif action == "CLOSE":
        t = st.session_state.active_trade
        pnl = (price - t['entry']) / t['entry']
        if t['side'] == "SHORT": pnl *= -1
        profit = t['amt'] * pnl
        st.session_state.wallet += profit
        st.session_state.history.append({'Idő': datetime.now().strftime("%H:%M"), 'Típus': t['side'], 'Profit': f"{profit:+.0f} Ft"})
        st.session_state.active_trade = None

# =================================================================
# 4. FŐ DASHBOARD FUTTATÁSA
# =================================================================
df = load_market_data()

if df is not None:
    curr_p = df['Close'].iloc[-1]
    pred_p = get_ai_prediction(df)
    sent_val, news = get_sentiment()
    diff = pred_p - curr_p
    
    # --- SZIGNÁL FÚZIÓ SZÁMÍTÁSA ---
    # ML irány (50%) + Szentiment (50%)
    ml_score = 100 if pred_p > curr_p else 0
    buy_pct = (ml_score * 0.5) + (sent_val * 100 * 0.5)
    sell_pct = 100 - buy_pct

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Robot Kontroll")
        risk_val = st.slider("Kockázat (% tőke)", 0, 100, 75)
        threshold = st.slider("AI Küszöb (USD)", 0.05, 0.50, 0.10)
        st.session_state.ai_broker = st.toggle("🤖 AI BRÓKER AKTÍV", value=st.session_state.ai_broker)
        if st.button("RESETPORTFOLIO"):
            st.session_state.wallet = 1000000.0
            st.session_state.history = []
            st.rerun()

    # 1. PÉNZTÁRCA
    glow = "ai-glow" if st.session_state.ai_broker else ""
    st.markdown(f"""<div class="wallet-header {glow}"><h3 style="color:#f1c40f;margin:0;">SZIMULÁLT EGYENLEG</h3><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>""", unsafe_allow_html=True)

    # 2. MOBIL RÁCS
    t_hu = datetime.now(pytz.timezone('Europe/Budapest')).strftime("%H:%M:%S")
    st.markdown(f"""
        <div class="mobile-grid">
            <div class="stat-card"><span class="stat-label">Budapest</span><span class="stat-value">{t_hu}</span></div>
            <div class="stat-card"><span class="stat-label">Brent Ár</span><span class="stat-value">${curr_p:.2f}</span></div>
            <div class="stat-card"><span class="stat-label">ML Célár</span><span class="stat-value">${pred_p:.2f}</span></div>
            <div class="stat-card"><span class="stat-label">Hír Index</span><span class="stat-value">{sent_val:.2f}</span></div>
        </div>
    """, unsafe_allow_html=True)

    # 3. NAGY SZÁZALÉKOS SZIGNÁL PANEL
    if buy_pct > 65: status, color = "ERŐS VÉTEL! 🚀", "#2ecc71"
    elif sell_pct > 65: status, color = "ERŐS ELADÁS! 📉", "#e74c3c"
    else: status, color = "VÁRAKOZÁS ⚖️", "#95a5a6"

    st.markdown(f"""<div class="signal-box" style="background-color: {color};">
        <div class="signal-title">{status}</div>
        <div style="color: white; font-weight: bold; font-size: 20px;">VÉTEL: {buy_pct:.1f}% | ELADÁS: {sell_pct:.1f}%</div>
    </div>""", unsafe_allow_html=True)

    # AI BRÓKER LOGIKA
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

    # 4. GRAFIKON
    fig = go.Figure()
    p_df = df.tail(60)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['Close'], name="Ár", line=dict(color='white', width=1.5)))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        scol = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        mask = p_df.index >= t['time'].replace(tzinfo=None)
        segment = p_df[mask]
        if not segment.empty:
            fig.add_trace(go.Scatter(x=segment.index, y=segment['Close'], line=dict(color=scol, width=6), name="ÜZLET"))
        fig.add_hline(y=t['entry'], line_dash="dash", line_color="yellow")

    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='#0e1117', plot_bgcolor='#0e1117')
    st.plotly_chart(fig, use_container_width=True)

    # 5. HÍREK ÉS NAPLÓ
    st.subheader("📰 Piaci Hangulat & Hírek")
    for n in news: st.caption(f"• {n}")
    
    if st.session_state.history: 
        st.subheader("📜 Előzmények")
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(30)
    st.rerun()

else:
    st.warning("⚠️ NINCS ADAT. A tőzsde valószínűleg zárva van vagy szünetel.")
    time.sleep(60)
    st.rerun()
