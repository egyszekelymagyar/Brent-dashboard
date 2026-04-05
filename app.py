import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="Brent Olaj Dashboard", layout="wide")
st.title("Brent olaj ár és jelzések")

# ---- Adatlekérés (Yahoo Finance) ----
@st.cache_data(ttl=300)
def get_brent_data():
    try:
        data = yf.download("BZ=F", period="6mo", interval="1d")
        data = data.reset_index()
        data = data[['Date', 'Close']]
        data.columns = ['date', 'price']
        return data
    except Exception as e:
        st.error(f"Hiba az adatlekérésnél: {e}")
        return pd.DataFrame({'date':[], 'price':[]})

df = get_brent_data()

if df.empty:
    st.error("Nincs adat.")
    st.stop()

# ---- Indikátorok ----
df['RSI'] = ta.rsi(df['price'], length=14)

macd = ta.macd(df['price'])
df['MACD'] = macd['MACD_12_26_9']

bb = ta.bbands(df['price'])
df['BB_upper'] = bb['BBU_20_2.0']
df['BB_lower'] = bb['BBL_20_2.0']

# ---- Grafikon ----
fig, ax = plt.subplots(figsize=(10,4))
ax.plot(df['date'], df['price'], label='Ár', color='blue')

# Buy/Sell pontok
buy = df[(df['RSI'] < 30) | (df['price'] < df['BB_lower'])]
sell = df[(df['RSI'] > 70) | (df['price'] > df['BB_upper'])]

ax.scatter(buy['date'], buy['price'], color='green', label='Buy', marker='^')
ax.scatter(sell['date'], sell['price'], color='red', label='Sell', marker='v')

ax.legend()
ax.set_title("Brent ár és jelzések")
st.pyplot(fig)

# ---- Jelzések ----
st.subheader("Jelzések")

rsi_signal = "Hold"
if df['RSI'].iloc[-1] < 30:
    rsi_signal = "Buy"
elif df['RSI'].iloc[-1] > 70:
    rsi_signal = "Sell"

macd_signal = "Hold"
if df['MACD'].iloc[-1] > 0:
    macd_signal = "Buy"
elif df['MACD'].iloc[-1] < 0:
    macd_signal = "Sell"

bb_signal = "Hold"
if df['price'].iloc[-1] < df['BB_lower'].iloc[-1]:
    bb_signal = "Buy"
elif df['price'].iloc[-1] > df['BB_upper'].iloc[-1]:
    bb_signal = "Sell"

signals = [rsi_signal, macd_signal, bb_signal]

buy_count = signals.count("Buy")
sell_count = signals.count("Sell")

overall = "Hold"
if buy_count > sell_count:
    overall = "Buy"
elif sell_count > buy_count:
    overall = "Sell"

st.write(f"RSI: {rsi_signal}")
st.write(f"MACD: {macd_signal}")
st.write(f"Bollinger: {bb_signal}")
st.write(f"Összesített jelzés: {overall}")

# ---- Egyszerű előrejelzés (trend alapú) ----
st.subheader("Egyszerű előrejelzés")

last_prices = df['price'].tail(5)
trend = np.polyfit(range(len(last_prices)), last_prices, 1)[0]

future = []
last_price = df['price'].iloc[-1]

for i in range(7):
    last_price += trend
    future.append(last_price)

future_dates = pd.date_range(df['date'].iloc[-1], periods=8)[1:]

forecast_df = pd.DataFrame({
    'date': future_dates,
    'forecast': future
})

st.line_chart(forecast_df.set_index('date'))

st.success(f"Frissítve: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
