import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import requests

st.set_page_config(page_title="Brent High-Frequency Dashboard", layout="wide")

# --- ADATBETÖLTÉS (PERC ALAPÚ) ---
@st.cache_data(ttl=60) # Percenként frissítünk
def load_intraday_data():
    # 1 perces adatok az utolsó 7 napról (Yahoo limit)
    data = yf.download("BZ=F", period="7d", interval="1m")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

try:
    df = load_intraday_data()
    
    # INDIKÁTOROK (Perc alapú beállításokhoz igazítva)
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain / loss)))

    # --- TREND ANALÍZIS ÉS A NAGY MEZŐ ---
    latest = df.iloc[-1]
    score = 0
    if latest["RSI"] < 35: score += 1
    elif latest["RSI"] > 65: score -= 1
    if latest["Close"] > latest["EMA_20"]: score += 1
    else: score -= 1
    
    if score >= 1: 
        signal_text, signal_color = "ERŐS EMELKEDÉS (BULLISH)", "#2ecc71"
    elif score <= -1: 
        signal_text, signal_color = "ERŐS CSÖKKENÉS (BEARISH)", "#e74c3c"
    else: 
        signal_text, signal_color = "OLDALAZÁS / BIZONYTALAN", "#bdc3c7"

    # UI: Státusz mező visszahozása
    st.markdown(f"""
        <div style="background-color:{signal_color}; padding:30px; border-radius:15px; text-align:center; margin-bottom:20px;">
            <h1 style="color:white; margin:0; font-size:40px;">{signal_text}</h1>
            <p style="color:white; font-size:20px; opacity:0.9;">Aktuális Brent Ár: ${float(latest['Close']):.2f} | Trend Score: {score}</p>
        </div>
        """, unsafe_allow_html=True)

    # --- SZIMULÁCIÓ / BACKTEST (Tegnap vs Ma) ---
    st.subheader("🔮 Előrejelzés Szimuláció (Backtest)")
    
    # 1. Tanulás a múltból (az utolsó előtti nap végéig)
    train_data = df.iloc[:-1440] # Levágjuk az utolsó 1 napnyi percet (kb 1440 perc)
    test_data = df.iloc[-1440:]   # Ez a "valóság", amit ellenőrzünk
    
    model = LinearRegression()
    X_train = np.arange(len(train_data)).reshape(-1, 1)
    model.fit(X_train, train_data["Close"])
    
    # 2. Jóslat készítése a teszt időszakra
    X_test = np.arange(len(train_data), len(train_data) + len(test_data)).reshape(-1, 1)
    predictions = model.predict(X_test)
    
    # 3. Vizualizáció
    fig_sim = go.Figure()
    # Valóság
    fig_sim.add_trace(go.Scatter(x=test_data.index, y=test_data['Close'], name="Tényleges árfolyam", line=dict(color="#3498db")))
    # Modell várakozása
    fig_sim.add_trace(go.Scatter(x=test_data.index, y=predictions, name="Program előzetes várakozása", line=dict(color="#e67e22", dash="dash")))
    
    fig_sim.update_layout(title="Hogy teljesített a modell az elmúlt 24 órában?", template="plotly_white", height=400)
    st.plotly_chart(fig_sim, use_container_width=True)

    # --- INTERAKTÍV PERC ALAPÚ GRAFIKON ---
    st.subheader("📈 Élő Percenkénti Adatok (Utolsó 7 nap)")
    fig_main = go.Figure()
    fig_main.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Brent Ár', line=dict(color='#2c3e50')))
    fig_main.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], name='Trend (EMA 20)', line=dict(color='#f1c40f', width=1)))
    fig_main.update_layout(template="plotly_white", height=500, hovermode="x unified")
    st.plotly_chart(fig_main, use_container_width=True)

    # --- TELEGRAM ---
    if st.button("🚨 Jelzés küldése"):
        # Itt hagyd meg a korábbi Telegram kódot a Tokenjeiddel!
        st.write("Telegram küldés funkció kész...")

except Exception as e:
    st.error(f"Hiba: {e}")
    st.info("A Yahoo Finance néha korlátozza a percenkénti lekérést. Ha nem tölt be, várj 1 percet.")
