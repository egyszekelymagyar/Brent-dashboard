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
TELEGRAM_TOKEN = ""   # ide jön majd
TELEGRAM_CHAT_ID = "" # ide jön majd

# --- ADAT ---
@st.cache_data
def load_data():
    df = yf.download("BZ=F", period="6mo", interval="1d")
    return df.dropna()

df = load_data()

# --- INDIKÁTOROK ---
def add_indicators(df):
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["EMA_20"] = df["Close"].ewm(span=20).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df

df = add_indicators(df)

# --- SIGNAL ---
def get_signal(df):
    latest = df.iloc[-1]

    if latest["RSI"] < 30:
        return "BUY"
    elif latest["RSI"] > 70:
        return "SELL"
    else:
        return "HOLD"

signal = get_signal(df)

# --- TELEGRAM ---
def send_telegram(msg):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

# --- GRAFIKON ---
st.subheader("Ár + indikátorok")

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(df.index, df["Close"], label="Ár")
ax.plot(df.index, df["SMA_20"], label="SMA 20")
ax.plot(df.index, df["EMA_20"], label="EMA 20")
ax.legend()

st.pyplot(fig)

# --- RSI ---
st.subheader("RSI")

fig2, ax2 = plt.subplots(figsize=(10, 3))
ax2.plot(df.index, df["RSI"], label="RSI")
ax2.axhline(70, linestyle="--")
ax2.axhline(30, linestyle="--")
ax2.legend()

st.pyplot(fig2)

# --- SIGNAL KIÍRÁS ---
st.subheader("Jelzés")

st.write("Aktuális jel:", signal)

if st.button("Küldés Telegramra"):
    send_telegram(f"Brent jelzés: {signal}")

# --- ELŐREJELZÉS ---
st.subheader("Előrejelzés")

df_pred = df.copy()
df_pred["t"] = np.arange(len(df_pred))

model = LinearRegression()
model.fit(df_pred[["t"]], df_pred["Close"])

future_days = 5
future_t = np.arange(len(df_pred), len(df_pred)+future_days).reshape(-1,1)
pred = model.predict(future_t)

future_dates = pd.date_range(start=df.index[-1], periods=future_days+1)[1:]

fig3, ax3 = plt.subplots(figsize=(10,5))
ax3.plot(df.index, df["Close"], label="Valós")
ax3.plot(future_dates, pred, label="Előrejelzés")
ax3.legend()

st.pyplot(fig3)

# --- HÍREK ---
st.subheader("Olaj hírek")

def get_news():
    url = "https://newsapi.org/v2/everything?q=oil&language=en&pageSize=5&apiKey=YOUR_API_KEY"
    try:
        r = requests.get(url).json()
        return r.get("articles", [])
    except:
        return []

news = get_news()

for n in news:
    st.write("**", n["title"], "**")
    st.write(n["url"])

# --- INFO ---
st.subheader("Utolsó ár")
st.write(df["Close"].iloc[-1])
