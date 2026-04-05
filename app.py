import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="Brent Dashboard", layout="wide")

st.title("Brent olaj dashboard")

# --- ADAT LETÖLTÉS ---
@st.cache_data
def load_data():
    df = yf.download("BZ=F", period="6mo", interval="1d")
    df = df.dropna()
    return df

df = load_data()

# --- INDIKÁTOROK ---
def add_indicators(df):
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

# --- GRAFIKON ---
st.subheader("Árfolyam + indikátorok")

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

# --- ELŐREJELZÉS (egyszerű) ---
st.subheader("Egyszerű előrejelzés")

df_pred = df.copy()
df_pred["t"] = np.arange(len(df_pred))

X = df_pred[["t"]]
y = df_pred["Close"]

model = LinearRegression()
model.fit(X, y)

future_days = 5
future_t = np.arange(len(df_pred), len(df_pred) + future_days).reshape(-1, 1)
predictions = model.predict(future_t)

future_dates = pd.date_range(start=df.index[-1], periods=future_days + 1)[1:]

fig3, ax3 = plt.subplots(figsize=(10, 5))
ax3.plot(df.index, df["Close"], label="Valós ár")
ax3.plot(future_dates, predictions, label="Előrejelzés")

ax3.legend()
st.pyplot(fig3)

# --- INFO ---
st.subheader("Utolsó ár")
st.write(df["Close"].iloc[-1])
