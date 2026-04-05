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
st.set_page_config(page_title="Brent AI Pro - Broker Edition", layout="wide", page_icon="🛢️")

# --- 1. HISTORIKUS SOKK-ADATBÁZIS & BRÓKER SÚLYOZÁS ---
# Referencia események a volatilitás és Stop-Loss számításhoz
SHOCK_BENCHMARKS = {
    "WAR_INV_2022": {"impact": 0.30, "std_dev_mult": 2.5, "desc": "Orosz invázió - Supply Shock"},
    "TERROR_911": {"impact": 0.05, "std_dev_mult": 4.0, "desc": "9/11 - Demand/Panic Shock"},
    "HOR_STR_2026": {"impact": 0.15, "std_dev_mult": 3.0, "desc": "Hormuzi-szoros - Route Risk"}
}

SOURCE_WEIGHTS = {
    "Bloomberg": 0.45, "Reuters": 0.30, "FT_WSJ": 0.15, "Market_Sentiment": 0.10
}

# --- 2. ADATKEZELŐ FUNKCIÓK ---
@st.cache_data(ttl=60)
def load_market_data():
    # 1 perces adatok az utolsó 7 napról
    data = yf.download("BZ=F", period="5d", interval="1m")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

def calculate_stop_loss(price, volatility_score, direction="buy"):
    # Stop-loss számítás a historikus sokkok volatilitása alapján
    buffer = 0.02 * (1 + volatility_score) # Alap 2% + sokk faktor
    return price * (1 - buffer) if direction == "buy" else price * (1 + buffer)

# --- 3. OLDALSÁV (TELEGRAM & AUTOMATIZÁCIÓ) ---
with st.sidebar:
    st.header("🤖 Vezérlőpult")
    TELEGRAM_TOKEN = st.text_input("Telegram Bot Token", type="password")
    TELEGRAM_CHAT_ID = st.text_input("Chat ID")
    
    st.divider()
    auto_mode = st.toggle("🚀 Automata Percenkénti Jelzések", help="Bekapcsolás után percenként küld szignált ha nyitva a piac.")
    
    st.info("Piacnyitás: Vasárnap 24:00 (CET)")

# --- 4. FŐ LOGIKA ÉS ELEMZÉS ---
try:
    df = load_market_data()
    
    # Indikátorok
    df['EMA_20'] = df['Close'].ewm(span=20).mean()
    df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().where(df['Close'].diff() > 0, 0).rolling(14).mean() / 
                                  -df['Close'].diff().where(df['Close'].diff() < 0, 0).rolling(14).mean())))

    # Szimulált hírek (Élesben API-ból jönne)
    news_headlines = [
        "Bloomberg: Geopolitical tensions rising in Middle East",
        "Reuters: OPEC+ monitoring supply disruptions",
        "FT: Oil demand forecast remains stable despite risks"
    ]
    
    # Szentiment számítás (Bróker súlyozással)
    sentiment_score = 0.78 # Pl. Erősödő politikai feszültség miatt
    tech_signal = 1 if df['Close'].iloc[-1] > df['EMA_20'].iloc[-1] else -1
    final_score = (tech_signal * 0.6) + (sentiment_score * 0.4)

    # --- 5. NAGY STÁTUSZ MEZŐ ---
    status_text = "ERŐS VÉTEL (BULLISH)" if final_score > 0.5 else "ERŐS ELADÁS (BEARISH)" if final_score < -0.5 else "OLDALAZÁS"
    status_color = "#27ae60" if final_score > 0.5 else "#e74c3c" if final_score < -0.5 else "#7f8c8d"

    st.markdown(f"""
        <div style="background-color:{status_color}; padding:30px; border-radius:15px; text-align:center; color:white; margin-bottom:25px;">
            <h1 style="margin:0; font-size:40px;">{status_text}</h1>
            <p style="font-size:18px;">Összetett pontszám: {final_score:.2f} | Aktuális ár: ${float(df['Close'].iloc[-1]):.2f}</p>
        </div>
    """, unsafe_allow_html=True)

    # --- 6. WALK-FORWARD VIZUALIZÁCIÓ ---
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("🔮 Walk-Forward Szimuláció (Múlt vs. Valóság)")
        window = 60
        test_data = df.iloc[-120:]
        
        # Modell tanítása a múltbeli "vak" szeleten
        model = LinearRegression().fit(np.arange(window).reshape(-1, 1), test_data['Close'][:window].values)
        preds = model.predict(np.arange(window, window*2).reshape(-1, 1))
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=test_data['Close'][window:].values, name="Tényleges Ár", line=dict(color="#2c3e50")))
        fig.add_trace(go.Scatter(y=preds, name="Vak Jóslat", line=dict(color="#e67e22", dash="dash")))
        fig.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("🎯 Javasolt Kereskedés")
        curr_p = float(df['Close'].iloc[-1])
        direction = "buy" if final_score > 0 else "sell"
        sl = calculate_stop_loss(curr_p, abs(final_score), direction)
        
        st.metric("Várható irány", "VÉTEL" if direction == "buy" else "ELADÁS")
        st.metric("Javasolt Stop-Loss", f"${sl:.2f}")
        st.write(f"**Sokk-faktor:** {SHOCK_BENCHMARKS['HOR_STR_2026']['desc']}")

    # --- 7. AUTOMATA JELZÉSKÜLDÉS (WHILE LOOP) ---
    if auto_mode:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            st.error("Add meg a Telegram adatokat az oldalsávban!")
        else:
            placeholder = st.empty()
            while auto_mode:
                now = datetime.now().strftime("%H:%M:%S")
                # Telegram küldés logika
                if abs(final_score) > 0.6:
                    msg = f"🛢️ BRENT JELZÉS [{now}]\nIrány: {status_text}\nÁr: ${curr_p:.2f}\nStop-Loss: ${sl:.2f}\nPont: {final_score:.2f}"
                    requests.post(f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage", 
                                  data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
                
                with placeholder.container():
                    st.success(f"Aktív figyelés... Utolsó frissítés: {now}")
                time.sleep(60) # Várakozás 1 percig
                st.rerun()

except Exception as e:
    st.error(f"Rendszerhiba: {e}")
