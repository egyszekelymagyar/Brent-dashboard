import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz
import time
from sklearn.ensemble import RandomForestRegressor

# --- 1. KONFIGURÁCIÓ ÉS MEMÓRIA ---
st.set_page_config(page_title="BRENT AI - MASTER TRADER", layout="wide")

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
    .wallet-card { background: linear-gradient(90deg, #161b22, #232d39); border: 2px solid #f1c40f; padding: 15px; border-radius: 12px; text-align: center; }
    .ai-glow { border: 2px solid #00d4ff; box-shadow: 0px 0px 20px rgba(0, 212, 255, 0.4); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ADAT ÉS ML MOTOR ---
@st.cache_data(ttl=30)
def load_data():
    df = yf.download("BZ=F", period="2d", interval="1m", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df.dropna()

def get_prediction(df):
    data = df.tail(150).copy()
    data['Target'] = data['Close'].shift(-1)
    data = data.dropna()
    X = data[['Open', 'High', 'Low', 'Close']].values
    y = data['Target'].values
    model = RandomForestRegressor(n_estimators=50, random_state=42).fit(X[:-1], y[:-1])
    return model.predict(X[-1].reshape(1, -1))[0]

# --- 3. OLDALSÁV (VEZÉRLÉS ÉS CSÚSZKA) ---
with st.sidebar:
    st.header("⚙️ Robot Beállítások")
    risk_pct = st.slider("Kockázati Szint (% tőke)", 0, 100, 75)
    entry_threshold = st.slider("Belépési Küszöb (USD)", 0.05, 0.30, 0.10, step=0.01)
    st.divider()
    st.session_state.ai_broker = st.toggle("🤖 AI BRÓKER AKTIVÁLÁSA", value=st.session_state.ai_broker)
    st.info(f"Kiválasztott kockázat: {risk_pct}% ({st.session_state.wallet * (risk_pct/100):,.0f} Ft)")

# --- 4. KERESKEDÉSI FUNKCIÓK ---
def open_trade(side, price, risk_ratio):
    investment = st.session_state.wallet * (risk_ratio / 100)
    st.session_state.active_trade = {
        'side': side,
        'entry_price': price,
        'entry_time': datetime.now(pytz.timezone('Europe/Budapest')),
        'amount_huf': investment
    }

def close_trade(current_price):
    trade = st.session_state.active_trade
    pnl_pct = (current_price - trade['entry_price']) / trade['entry_price']
    if trade['side'] == "SHORT": pnl_pct *= -1
    
    profit_huf = trade['amount_huf'] * pnl_pct
    st.session_state.wallet += profit_huf
    st.session_state.history.append({
        'Idő': datetime.now().strftime("%H:%M"),
        'Típus': trade['side'],
        'Profit': f"{profit_huf:+.0f} Ft",
        'Egyenleg': f"{st.session_state.wallet:,.0f} Ft"
    })
    st.session_state.active_trade = None

# --- 5. LOGIKA ÉS DASHBOARD ---
df = load_data()
pred_p = get_prediction(df)
curr_p = df['Close'].iloc[-1]
diff = pred_p - curr_p

# Egyenleg kártya
ai_class = "ai-glow" if st.session_state.ai_broker else ""
st.markdown(f"""<div class="wallet-card {ai_class}"><h3 style="color: #f1c40f; margin:0;">SZIMULÁLT EGYENLEG</h3><h1 style="color: white; margin:0;">{st.session_state.wallet:,.0f} Ft</h1></div>""", unsafe_allow_html=True)

# AI BRÓKER DÖNTÉS
if st.session_state.ai_broker:
    if not st.session_state.active_trade:
        if diff > entry_threshold: open_trade("LONG", curr_p, risk_pct)
        elif diff < -entry_threshold: open_trade("SHORT", curr_p, risk_pct)
    else:
        t = st.session_state.active_trade
        # Zárás ha ellentétes szignál érkezik
        if (t['side'] == "LONG" and diff < -0.02) or (t['side'] == "SHORT" and diff > 0.02):
            close_trade(curr_p)

# Manuális Gombok
if not st.session_state.ai_broker:
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🚀 LONG (VÉTEL)", use_container_width=True): open_trade("LONG", curr_p, risk_pct)
    with c2: 
        if st.button("📉 SHORT (ELADÁS)", use_container_width=True): open_trade("SHORT", curr_p, risk_pct)
    with c3: 
        if st.button("❌ ZÁRÁS", use_container_width=True): close_trade(curr_p)

# --- 6. GRAFIKON ---
fig = go.Figure()
plot_df = df.tail(60)
fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Close'], name="Ár", line=dict(color='white', width=1.5)))

if st.session_state.active_trade:
    t = st.session_state.active_trade
    color = "#2ecc71" if t['side'] == "LONG" else "#e74c3c"
    fig.add_hline(y=t['entry_price'], line_dash="dash", line_color="yellow", annotation_text="BELÉPŐ")
    
    # Aktív szakasz kiemelése
    trade_mask = plot_df.index >= t['entry_time'].replace(tzinfo=None)
    trade_segment = plot_df[trade_mask]
    if not trade_segment.empty:
        fig.add_trace(go.Scatter(x=trade_segment.index, y=trade_segment['Close'], line=dict(color=color, width=6), name="ÜZLETBEN"))

fig.update_layout(template="plotly_dark", height=420, margin=dict(l=0,r=0,t=10,b=0))
st.plotly_chart(fig, use_container_width=True)

# Alsó státusz és napló
if st.session_state.active_trade:
    t = st.session_state.active_trade
    pnl = (curr_p - t['entry_price']) if t['side'] == "LONG" else (t['entry_price'] - curr_p)
    st.markdown(f"📍 **Aktív pozíció:** {t['side']} | **Befektetve:** {t['amount_huf']:,.0f} Ft | **P&L:** `${pnl:+.4f}`")

if st.session_state.history:
    st.subheader("📜 Utolsó ügyletek")
    st.table(pd.DataFrame(st.session_state.history).tail(5))

time.sleep(30)
st.rerun()
