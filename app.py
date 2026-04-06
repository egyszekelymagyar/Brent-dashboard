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
# 1. KONFIGURÁCIÓ ÉS MEMÓRIA (TÖRVÉNY: MINDEN RÉGI FUNKCIÓ MARAD)
# =================================================================
st.set_page_config(page_title="BRENT AI - MASTER HYBRID", layout="wide", page_icon="🏦")

if 'wallet' not in st.session_state: st.session_state.wallet = 1000000.0
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'history' not in st.session_state: st.session_state.history = []
if 'ai_broker' not in st.session_state: st.session_state.ai_broker = False

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .mobile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .stat-card { background-color: #1a1c24; border: 2px solid #30363d; padding: 10px; border-radius: 10px; text-align: center; }
    .stat-label { color: #FFFFFF; font-size: 11px; font-weight: 800; text-transform: uppercase; display: block; }
    .stat-value { color: #00ffcc; font-size: 18px; font-weight: 900; display: block; }
    .wallet-header { background: linear-gradient(90deg, #161b22, #232d39); border: 2px solid #f1c40f; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 15px; }
    .ai-glow { border: 2px solid #00d4ff; box-shadow: 0px 0px 20px rgba(0, 212, 255, 0.6); }
    .signal-box { padding: 25px; border-radius: 15px; text-align: center; border: 4px solid #ffffff; margin-bottom: 15px; }
    .signal-title { font-size: 35px !important; color: #ffffff !important; font-weight: 900; margin: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS ML MOTOR (JAVÍTOTT IDŐZÓNA KEZELÉS)
# =================================================================
@st.cache_data(ttl=30)
def load_market_data():
    try:
        df = yf.download("BZ=F", period="2d", interval="1m", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        # TÖRVÉNY: A grafikon indexét tz-naive-re alakítjuk a színezéshez
        df.index = df.index.tz_localize(None)
        return df.dropna()
    except: return None

def get_ai_prediction(df):
    data = df.tail(150).copy()
    data['Target'] = data['Close'].shift(-1)
    data = data.dropna()
    X, y = data[['Open', 'High', 'Low', 'Close']].values, data['Target'].values
    model = RandomForestRegressor(n_estimators=100, random_state=42).fit(X[:-1], y[:-1])
    return model.predict(X[-1].reshape(1, -1))[0]

# =================================================================
# 3. KERESKEDÉSI FUNKCIÓK (ENGEDÉLYEZETT ÚJÍTÁSOK)
# =================================================================
def manage_trade(action, side, price, risk=75):
    if action == "OPEN":
        inv = st.session_state.wallet * (risk / 100)
        # Mentjük a belépési időpontot tz-naive formátumban a grafikonhoz
        st.session_state.active_trade = {
            'side': side, 'entry': price, 'amt': inv, 
            'time': datetime.now() 
        }
    elif action == "CLOSE":
        if st.session_state.active_trade:
            t = st.session_state.active_trade
            pnl = (price - t['entry']) / t['entry']
            if t['side'] == "SHORT": pnl *= -1
            profit = t['amt'] * pnl
            st.session_state.wallet += profit
            st.session_state.history.append({'Típus': t['side'], 'Profit': f"{profit:+.0f} Ft"})
            st.session_state.active_trade = None

# =================================================================
# 4. FŐ PROGRAMFUTÁS
# =================================================================
df = load_market_data()

if df is not None:
    curr_p = df['Close'].iloc[-1]
    pred_p = get_ai_prediction(df)
    diff = pred_p - curr_p
    
    # SZÁZALÉKOS SZIGNÁL (TÖRVÉNY: MARADT)
    buy_pct = 100 if pred_p > curr_p else 0 # Egyszerűsített de határozott ML szignál
    sell_pct = 100 - buy_pct

    # --- VEZÉRLŐPULT (SIDEBAR) ---
    with st.sidebar:
        st.header("⚙️ Beállítások")
        # ÚJ: Robot Üzemmód Kapcsoló
        st.session_state.ai_broker = st.toggle("🤖 ROBOT ÜZEMMÓD (AUTO)", value=st.session_state.ai_broker)
        risk_val = st.slider("Kockázat (%)", 10, 100, 75)
        # ÚJ: Agresszívabb küszöb (Hosszabb távú tartás)
        threshold = st.slider("Belépési Küszöb (USD)", 0.05, 0.50, 0.15)
        st.divider()
        if st.button("RESET"):
            st.session_state.wallet = 1000000.0
            st.session_state.history = []
            st.rerun()

    # 1. PÉNZTÁRCA (TÖRVÉNY: MARADT)
    glow = "ai-glow" if st.session_state.ai_broker else ""
    st.markdown(f"""<div class="wallet-header {glow}"><h3 style="color:#f1c40f;margin:0;">EGYENLEG</h3><h1 style="color:white;margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>""", unsafe_allow_html=True)

    # 2. MOBIL RÁCS (TÖRVÉNY: MARADT)
    t_hu = datetime.now(pytz.timezone('Europe/Budapest')).strftime("%H:%M:%S")
    st.markdown(f"""<div class="mobile-grid">
        <div class="stat-card"><span class="stat-label">Budapest</span><span class="stat-value">{t_hu}</span></div>
        <div class="stat-card"><span class="stat-label">Ár</span><span class="stat-value">${curr_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">ML Cél</span><span class="stat-value">${pred_p:.2f}</span></div>
        <div class="stat-card"><span class="stat-label">Vétel %</span><span class="stat-value">{buy_pct}%</span></div>
    </div>""", unsafe_allow_html=True)

    # 3. SZIGNÁL ÉS GOMBOK (ENGEDÉLYEZETT ÚJÍTÁSOK)
    status = "VÉTEL! 🚀" if buy_pct > 50 else "ELADÁS! 📉"
    color = "#2ecc71" if buy_pct > 50 else "#e74c3c"
    st.markdown(f"""<div class="signal-box" style="background-color: {color};"><div class="signal-title">{status}</div></div>""", unsafe_allow_html=True)

    if st.session_state.ai_broker:
        # AGRESSZÍVEBB ROBOT LOGIKA
        if not st.session_state.active_trade:
            if diff > threshold: manage_trade("OPEN", "LONG", curr_p, risk_val)
            elif diff < -threshold: manage_trade("OPEN", "SHORT", curr_p, risk_val)
        else:
            # Csak akkor zár, ha a trend határozottan megfordul (hosszabb távú tartás)
            t = st.session_state.active_trade
            if (t['side'] == "LONG" and diff < -0.05) or (t['side'] == "SHORT" and diff > 0.05):
                manage_trade("CLOSE", None, curr_p)
    else:
        # ÚJ: MANUÁLIS GOMBOK (VÉTEL | ELADÁS | ZÁRÁS)
        c1, c2, c3 = st.columns(3)
        with c1: 
            if st.button("🚀 VÉTEL", use_container_width=True): manage_trade("OPEN", "LONG", curr_p, risk_val)
        with c2: 
            if st.button("📉 ELADÁS", use_container_width=True): manage_trade("OPEN", "SHORT", curr_p, risk_val)
        with c3: 
            # ÚJ: Kifejezett manuális zárás gomb
            if st.button("❌ ZÁRÁS", use_container_width=True): manage_trade("CLOSE", None, curr_p)

    # 4. GRAFIKON (JAVÍTOTT VIZUÁLIS SZAKASZ)
    fig = go.Figure()
    p_df = df.tail(100)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['Close'], name="Ár", line=dict(color='white', width=1.5)))

    if st.session_state.active_trade:
        t = st.session_state.active_trade
        scol = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
        # Belépési pont megkeresése és a vonal színezése
        mask = p_df.index >= t['time']
        segment = p_df[mask]
        
        if not segment.empty:
            # Vastag színezett szakasz a belépőtől
            fig.add_trace(go.Scatter(x=segment.index, y=segment['Close'], line=dict(color=scol, width=7), name="AKTÍV ÜGYLET"))
            # Sárga pont a belépési helyen
            fig.add_trace(go.Scatter(x=[segment.index[0]], y=[t['entry']], mode='markers', marker=dict(color='yellow', size=12, symbol='circle'), name="Belépő"))
        
        fig.add_hline(y=t['entry'], line_dash="dash", line_color="yellow", annotation_text="ENTRY")

    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='#0e1117', plot_bgcolor='#0e1117')
    st.plotly_chart(fig, use_container_width=True)

    # 5. ELŐZMÉNYEK
    if st.session_state.history:
        st.subheader("📜 Utolsó lezárt ügyletek")
        st.table(pd.DataFrame(st.session_state.history).tail(3))

    time.sleep(30)
    st.rerun()
else:
    st.warning("⏳ Adatkeresés... Kérlek várj!")
    time.sleep(10)
    st.rerun()
