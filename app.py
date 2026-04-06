import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import feedparser
import time
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime

# =================================================================
# 1. KONFIGURÁCIÓ
# =================================================================
st.set_page_config(page_title="BRENT AI PREDICATOR", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .prediction-card { background-color: #1a1c24; padding: 20px; border-radius: 15px; border: 2px solid #f1c40f; text-align: center; margin-bottom: 20px; }
    .signal-hero { padding: 30px; border-radius: 20px; text-align: center; margin-bottom: 20px; border: 3px solid white; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. ADAT ÉS GÉPI TANULÁS (ML) MOTOR
# =================================================================
@st.cache_data(ttl=60)
def get_data():
    df = yf.download("BZ=F", period="5d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()

def train_prediction_model(df):
    # Feature Engineering (Jellemzők kinyerése)
    df = df.copy()
    df['Sma_5'] = df['Close'].rolling(5).mean()
    df['Sma_20'] = df['Close'].rolling(20).mean()
    df['Vol_Change'] = df['Volume'].pct_change()
    df = df.dropna()
    
    # X (Múltbeli adatok), y (Következő Close ár)
    X = df[['Open', 'High', 'Low', 'Close', 'Sma_5', 'Sma_20']].values
    y = df['Close'].shift(-1).fillna(df['Close']).values # A cél a következő ár
    
    # Modell tanítása (Random Forest)
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X[:-1], y[:-1]) # Az utolsó sort kihagyjuk a tanításból
    
    # Jóslat az utolsó ismert adatsorból
    last_row = X[-1].reshape(1, -1)
    predicted_price = model.predict(last_row)[0]
    return predicted_price

# =================================================================
# 3. FŐ LOGIKA ÉS SZIGNÁL FÚZIÓ
# =================================================================
df = get_data()
pred_price = train_prediction_model(df)
curr_price = df.iloc[-1]['Close']
price_diff = pred_price - curr_price

# Hagyományos szentiment lekérése
feed = feedparser.parse("https://google.com")
sent_val = 0.5
for entry in feed.entries[:3]:
    if any(w in entry.title.lower() for w in ['cut', 'rise', 'shortage']): sent_val += 0.1
    if any(w in entry.title.lower() for w in ['drop', 'surplus', 'glut']): sent_val -= 0.1

# ÖSSZESÍTETT AI PONT (ML + SZENTIMENT)
# Ha a jósolt ár magasabb és a szentiment is jó -> Vétel
ml_signal = 1 if pred_price > curr_price else -1
final_score = (ml_signal * 40) + (sent_val * 100) # 0-100 skála környéke

# =================================================================
# 4. MEGJELENÍTÉS (UI)
# =================================================================
st.title("🤖 BRENT AI - MACHINE LEARNING TERMINAL")

col_top1, col_top2 = st.columns([1, 1])

with col_top1:
    direction = "EMELKEDÉS 📈" if pred_price > curr_price else "CSÖKKENÉS 📉"
    diff_pct = (price_diff / curr_price) * 100
    st.markdown(f"""<div class="prediction-card">
        <h3 style="color: #f1c40f; margin:0;">ML JÓSLAT (KÖV. 5 PERC)</h3>
        <h1 style="font-size: 45px; margin:10px;">${pred_price:.2f}</h1>
        <p style="font-size: 20px;">Várható irány: <b>{direction} ({diff_pct:+.2f}%)</b></p>
    </div>""", unsafe_allow_html=True)

with col_top2:
    if final_score > 75: status, color = "VÉTEL! 🚀", "#2ecc71"
    elif final_score < 45: status, color = "ELADÁS! 📉", "#e74c3c"
    else: status, color = "SEMLEGES ⚖️", "#34495e"
    
    st.markdown(f"""<div class="signal-hero" style="background-color: {color};">
        <h3 style="margin:0;">AI ÖSSZESÍTETT JELZÉS</h3>
        <h1 style="font-size: 45px; margin:10px;">{status}</h1>
        <p>Szentiment + ML Konfluencia: {final_score:.1f}%</p>
    </div>""", unsafe_allow_html=True)

# Grafikon
fig = go.Figure()
df_plot = df.tail(50)
fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="Brent"))
# Jósolt pont vizualizálása
fig.add_trace(go.Scatter(x=[df_plot.index[-1]], y=[pred_price], mode='markers', marker=dict(color='yellow', size=15, symbol='star'), name="Jósolt Ár"))
fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0))
st.plotly_chart(fig, use_container_width=True)

# Sidebar & Auto-refresh
with st.sidebar:
    st.header("⚙️ ML Kontroll")
    st.info("A modell 50 Random Forest fát használ a predikcióhoz.")
    refresh = st.toggle("Auto-Frissítés (30s)", value=True)
    if refresh:
        time.sleep(30)
        st.rerun()
