import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import requests
import time
from datetime import datetime

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="Brent AI Broker - Bi-Directional", layout="wide", page_icon="📉")

# --- 1. HISTORIKUS SOKK-ADATBÁZIS (Short & Long) ---
SHOCK_BENCHMARKS = {
    "WAR_INV_2022": {"impact": 0.30, "type": "Bullish"},
    "COVID_CRASH_2020": {"impact": -0.40, "type": "Bearish", "desc": "Demand Collapse"},
    "US_SHALE_BOOM": {"impact": -0.15, "type": "Bearish", "desc": "Supply Glut"}
}

# --- 2. ADATKEZELÉS ---
@st.cache_data(ttl=60)
def load_market_data():
    data = yf.download("BZ=F", period="5d", interval="1m")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

def calculate_levels(price, score, direction):
    # Dinamikus Stop-Loss és Take-Profit a volatilitás (score) alapján
    volatility_factor = abs(score) * 0.02
    if direction == "LONG (VÉTEL)":
        sl = price * (1 - (0.01 + volatility_factor))
        tp = price * (1 + (0.02 + volatility_factor))
    else: # SHORT (ELADÁS)
        sl = price * (1 + (0.01 + volatility_factor))
        tp = price * (1 - (0.02 + volatility_factor))
    return sl, tp

# --- 3. OLDALSÁV ---
with st.sidebar:
    st.header("⚙️ Rendszerbeállítások")
    TELEGRAM_TOKEN = st.text_input("Bot Token", type="password")
    TELEGRAM_CHAT_ID = st.text_input("Chat ID")
    st.divider()
    auto_mode = st.toggle("🚀 ÉLŐ PERCENKÉNTI SZIGNÁLOK")
    st.warning("Short és Long irányú elemzés aktív.")

# --- 4. ANALÍZIS ENGINE ---
try:
    df = load_market_data()
    df['EMA_Fast'] = df['Close'].ewm(span=12).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=26).mean()
    
    # RSI: Túladott (<30 = Vétel), Túlvett (>70 = Eladás/Short)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # --- KOMPLEX DÖNTÉSI LOGIKA (Long vs Short) ---
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Technikai pontszám (-3-tól +3-ig)
    tech_score = 0
    if latest['EMA_Fast'] > latest['EMA_Slow']: tech_score += 1 # Aranykereszt (Long)
    else: tech_score -= 1 # Halálkereszt (Short)
    
    if latest['RSI'] > 70: tech_score -= 1 # Túlvett (Short lehetőség)
    elif latest['RSI'] < 30: tech_score += 1 # Túladott (Long lehetőség)
    
    if latest['Close'] < prev['Close']: tech_score -= 1 # Csökkenő momentum
    else: tech_score += 1
    
    # Hír szentiment szimuláció (Bróker súlyozással)
    # Ha negatív hírek jönnek (pl. kínálatbővülés), ez lehúzza a pontszámot
    news_sentiment = -0.45 # Példa: Váratlan készletnövekedési hír (Short hír)
    
    # VÉGSŐ PONT (Súlyozva: 60% technika, 40% hír)
    final_score = (tech_score / 3 * 0.6) + (news_sentiment * 0.4)

    # --- 5. NAGY DINAMIKUS STÁTUSZ ---
    if final_score > 0.4:
        status, color = "ERŐS VÉTEL (LONG) 📈", "#27ae60"
        direction = "LONG (VÉTEL)"
    elif final_score < -0.4:
        status, color = "ERŐS ELADÁS (SHORT) 📉", "#e74c3c"
        direction = "SHORT (ELADÁS)"
    else:
        status, color = "VÁRAKOZÁS / SEMLEGES", "#7f8c8d"
        direction = "NONE"

    st.markdown(f"""
        <div style="background-color:{color}; padding:35px; border-radius:15px; text-align:center; color:white;">
            <h1 style="margin:0; font-size:48px;">{status}</h1>
            <p style="font-size:22px; opacity:0.9;">Kompozit Trend Index: {final_score:.2f} | Brent: ${latest['Close']:.2f}</p>
        </div>
    """, unsafe_allow_html=True)

    # --- 6. KERESKEDÉSI SZINTEK ---
    st.divider()
    c1, c2 = st.columns(2)
    sl, tp = calculate_levels(latest['Close'], final_score, direction)

    with c1:
        st.subheader("🎯 Aktuális Szignál Paraméterek")
        if direction != "NONE":
            st.write(f"**Irány:** {direction}")
            st.write(f"**Javasolt Stop-Loss:** <span style='color:red; font-weight:bold;'>${sl:.2f}</span>", unsafe_allow_html=True)
            st.write(f"**Célár (Take Profit):** <span style='color:green; font-weight:bold;'>${tp:.2f}</span>", unsafe_allow_html=True)
        else:
            st.write("Jelenleg nincs egyértelmű belépési pont. Várj a trendfordulóra.")

    with c2:
        st.subheader("📊 Momentum Ellenőrzés")
        fig_rsi = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = latest['RSI'],
            title = {'text': "RSI (Túlvett/Túladott)"},
            gauge = {'axis': {'range': [0, 100]},
                     'steps': [
                         {'range': [0, 30], 'color': "lightgreen"},
                         {'range': [70, 100], 'color': "salmon"}],
                     'threshold': {'line': {'color': "black", 'width': 4}, 'value': latest['RSI']}}))
        fig_rsi.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_rsi, use_container_width=True)

    # --- 7. AUTOMATA JELZÉS (TELEGRAM) ---
    if auto_mode and direction != "NONE":
        now = datetime.now().strftime("%H:%M:%S")
        msg = f"⚠️ BRENT PIACI JELZÉS [{now}]\n\n{status}\n💰 Ár: ${latest['Close']:.2f}\n🛑 Stop-Loss: ${sl:.2f}\n🎯 Célár: ${tp:.2f}\n📊 Pontszám: {final_score:.2f}"
        
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            # Csak 1 percenként egyszer küldünk, ha a pontszám jelentős
            if abs(final_score) > 0.6:
                requests.post(f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage", 
                              data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
                st.toast(f"Telegram szignál elküldve: {direction}")
        
        time.sleep(60)
        st.rerun()

except Exception as e:
    st.error(f"Adathiba: {e}. Valószínűleg zárva a tőzsde.")

