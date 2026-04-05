import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
import requests

st.set_page_config(page_title="Brent Dashboard", layout="wide")
st.title("Brent olaj – teljes dashboard")

# --- BEÁLLÍTÁSOK ---
TELEGRAM_TOKEN = ""   
TELEGRAM_CHAT_ID = "" 

# --- ADATBETÖLTÉS ---
@st.cache_data
def load_data():
    # Az auto_adjust és a MultiIndex kezelése miatt fixáljuk az oszlopokat
    data = yf.download("BZ=F", period="6mo", interval="1d")
    
    # JAVÍTÁS: Ha MultiIndex van (új yfinance hiba), leegyszerűsítjük
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    return data.dropna()

df_raw = load_data()
df = df_raw.copy()

# --- INDIKÁTOROK ---
def add_indicators(df):
    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df

df = add_indicators(df)

# --- SIGNAL SZÁMÍTÁS (HIBAJAVÍTÁSSAL) ---
def get_signal(df):
    # Csak azokat a sorokat nézzük, ahol már van RSI (nincs NaN)
    valid_df = df.dropna(subset=["RSI"])
    
    if valid_df.empty:
        return "NINCS ADAT"
    
    latest = valid_df.iloc[-1]
    rsi_val = latest["RSI"]

    if rsi_val < 30:
        return "BUY"
    elif rsi_val > 70:
        return "SELL"
    else:
        return "HOLD"

signal = get_signal(df)

# --- TELEGRAM ---
def send_telegram(msg):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        except:
            st.error("Telegram küldési hiba!")

# --- UI MEGJELENÍTÉS ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Ár + indikátorok")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df["Close"], label="Ár", color="blue")
    ax.plot(df.index, df["SMA_20"], label="SMA 20", alpha=0.7)
    ax.plot(df.index, df["EMA_20"], label="EMA 20", alpha=0.7)
    ax.legend()
    st.pyplot(fig)

with col2:
    st.subheader("RSI Indikátor")
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    ax2.plot(df.index, df["RSI"], label="RSI", color="purple")
    ax2.axhline(70, linestyle="--", color="red", alpha=0.5)
    ax2.axhline(30, linestyle="--", color="green", alpha=0.5)
    ax2.set_ylim(0, 100)
    ax2.legend()
    st.pyplot(fig2)

# --- SIGNAL ÉS TELEGRAM ---
st.divider()
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Aktuális jelzés", signal)
with c2:
    st.metric("Utolsó ár", f"{df['Close'].iloc[-1]:.2f} USD")
with c3:
    if st.button("Küldés Telegramra"):
        send_telegram(f"Brent jelzés: {signal} (Ár: {df['Close'].iloc[-1]:.2f})")
        st.success("Üzenet elküldve!")

# --- ELŐREJELZÉS (LINEAR REGRESSION) ---
st.subheader("Lineáris előrejelzés (5 nap)")
df_pred = df.dropna(subset=["Close"]).copy()
df_pred["t"] = np.arange(len(df_pred))

model = LinearRegression()
model.fit(df_pred[["t"]], df_pred["Close"])

future_days = 5
last_t = df_pred["t"].iloc[-1]
future_t = np.arange(last_t + 1, last_t + 1 + future_days).reshape(-1, 1)
pred = model.predict(future_t)

# Dátumok generálása a jövőre
future_dates = pd.date_range(start=df_pred.index[-1] + pd.Timedelta(days=1), periods=future_days)

fig3, ax3 = plt.subplots(figsize=(12, 4))
ax3.plot(df_pred.index[-30:], df_pred["Close"].iloc[-30:], label="Múltbeli ár")
ax3.plot(future_dates, pred, 'r--', label="Előrejelzés", marker='o')
ax3.legend()
st.pyplot(fig3)
