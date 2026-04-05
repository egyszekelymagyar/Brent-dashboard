import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
import requests

# Oldal konfiguráció
st.set_page_config(page_title="Brent Dashboard - Trend Analízis", layout="wide")

st.title("🛢️ Brent Olaj Dashboard & Trend Analízis")

# --- BEÁLLÍTÁSOK ---
TELEGRAM_TOKEN = ""   # Ide másold a BotFather-től kapott tokent
TELEGRAM_CHAT_ID = "" # Ide a saját Chat ID-dat
NEWS_API_KEY = "YOUR_API_KEY" # Opcionális: NewsAPI kulcs

# --- ADATBETÖLTÉS ÉS JAVÍTÁS ---
@st.cache_data
def load_data():
    # Adatok letöltése
    data = yf.download("BZ=F", period="1y", interval="1d")
    
    # 1. JAVÍTÁS: yfinance MultiIndex hiba elhárítása (ez okozta a ValueError-t)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Biztosítjuk, hogy ne legyenek üres sorok az elején
    return data.dropna()

try:
    df_raw = load_data()
    df = df_raw.copy()

    # --- INDIKÁTOROK SZÁMÍTÁSA ---
    def add_indicators(df):
        # Mozgóátlagok a trendhez
        df["SMA_20"] = df["Close"].rolling(window=20).mean()
        df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()

        # RSI számítás
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))
        return df

    df = add_indicators(df)

    # --- OKOS TREND ANALÍZIS ---
    def get_trend_analysis(df):
        # Csak azokat a sorokat nézzük, ahol minden indikátor kész
        valid_df = df.dropna(subset=["RSI", "SMA_20", "EMA_20"])
        
        if valid_df.empty:
            return "Nincs elég adat", "gray", 0
        
        latest = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        price = latest["Close"]
        rsi = latest["RSI"]
        ema = latest["EMA_20"]
        
        score = 0
        # 1. RSI alapú jelzés
        if rsi < 35: score += 1  # Túladott -> Vétel felé
        elif rsi > 65: score -= 1 # Túlvett -> Eladás felé
        
        # 2. Mozgóátlag trend (Ár az átlag felett = Emelkedő trend)
        if price > ema: score += 1
        else: score -= 1
        
        # 3. Rövid távú irány (Nőtt-e az ár tegnap óta?)
        if price > prev["Close"]: score += 1
        else: score -= 1

        # Kiértékelés
        if score >= 2: return "ERŐS EMELKEDÉS (BULLISH)", "#00ff00", score
        if score == 1: return "MÉRSÉKELT EMELKEDÉS", "#ccffcc", score
        if score <= -2: return "ERŐS CSÖKKENÉS (BEARISH)", "#ff0000", score
        if score == -1: return "MÉRSÉKELT CSÖKKENÉS", "#ffcccc", score
        return "OLDALAZÁS / BIZONYTALAN", "#cccccc", score

    signal_text, signal_color, score = get_trend_analysis(df)

    # --- UI ELRENDEZÉS ---
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Árfolyam és Indikátorok")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df.index, df["Close"], label="Záróár", color="blue", linewidth=2)
        ax.plot(df.index, df["SMA_20"], label="SMA 20 (Trend)", linestyle="--", alpha=0.7)
        ax.plot(df.index, df["EMA_20"], label="EMA 20 (Gyors)", alpha=0.7)
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)

    with col2:
        st.subheader("Várható Irány")
        st.markdown(f"""
            <div style="background-color:{signal_color}; padding:20px; border-radius:10px; text-align:center;">
                <h2 style="color:black; margin:0;">{signal_text}</h2>
                <p style="color:black; font-size:18px;">Trend pontszám: {score}</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.write("")
        st.metric("Aktuális Ár", f"{df['Close'].iloc[-1]:.2f} USD", f"{df['Close'].iloc[-1] - df['Close'].iloc[-2]:.2f}")
        st.metric("RSI Érték", f"{df['RSI'].iloc[-1]:.1f}")

    # --- ELŐREJELZÉS (LINEAR REGRESSION) ---
    st.divider()
    st.subheader("Lineáris Trend-előrejelzés (Következő 5 nap)")
    
    df_p = df.dropna(subset=["Close"]).copy()
    df_p["t"] = np.arange(len(df_p))
    
    model = LinearRegression()
    model.fit(df_p[["t"]], df_p["Close"])
    
    future_t = np.arange(len(df_p), len(df_p) + 5).reshape(-1, 1)
    future_preds = model.predict(future_t)
    future_dates = pd.date_range(start=df_p.index[-1] + pd.Timedelta(days=1), periods=5)

    fig2, ax2 = plt.subplots(figsize=(12, 3))
    ax2.plot(df_p.index[-20:], df_p["Close"].iloc[-20:], label="Múltbeli")
    ax2.plot(future_dates, future_preds, 'r--', marker='o', label="Becsült irány")
    ax2.legend()
    st.pyplot(fig2)

    # --- TELEGRAM ÉS HÍREK ---
    st.divider()
    c_left, c_right = st.columns(2)

    with c_left:
        if st.button("🚨 Jelzés küldése Telegramra"):
            msg = f"Brent Jelzés: {signal_text}\nÁr: {df['Close'].iloc[-1]:.2f} USD\nRSI: {df['RSI'].iloc[-1]:.1f}"
            if TELEGRAM_TOKEN:
                url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
                requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
                st.success("Sikeres küldés!")
            else:
                st.warning("Nincs megadva Telegram Token!")

    with c_right:
        st.write("**Elemzői megjegyzés:**")
        if score > 0:
            st.write("A technikai indikátorok alapján az árfolyamnak tere van a további emelkedésre.")
        else:
            st.write("A trend jelenleg gyengülést mutat, óvatosság javasolt a vétellel.")

except Exception as e:
    st.error(f"Hiba történt az adatok feldolgozása során: {e}")
    st.info("Tipp: Ellenőrizd az internetkapcsolatot vagy próbáld meg később, ha a Yahoo Finance szervere nem válaszol.")
