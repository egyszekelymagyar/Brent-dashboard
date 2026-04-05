# app.py
import streamlit as st
import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from transformers import pipeline
from newsapi import NewsApiClient
from datetime import datetime
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText

st.set_page_config(page_title="Brent Olaj Élő Dashboard", layout="wide")
st.title("Brent Olaj Élő Előrejelző Dashboard")

# Sidebar beállítások
st.sidebar.header("Riasztási beállítások")
price_thresh = st.sidebar.slider("Árváltozás küszöb (%)", 0.5, 10.0, 2.0, 0.1)/100
sentiment_thresh = st.sidebar.slider("Sentiment változás küszöb", 0.1, 1.0, 0.3, 0.05)

# Telegram
BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")
def send_telegram_alert(message):
    if BOT_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        except:
            st.warning("Telegram riasztás sikertelen")

# E-mail
EMAIL_USER = st.secrets.get("EMAIL_USER")
EMAIL_PASS = st.secrets.get("EMAIL_PASS")
TO_EMAIL = st.secrets.get("TO_EMAIL")
def send_email_alert(subject, body):
    if EMAIL_USER and EMAIL_PASS and TO_EMAIL:
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = EMAIL_USER
            msg['To'] = TO_EMAIL
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_USER, EMAIL_PASS)
                server.sendmail(EMAIL_USER, TO_EMAIL, msg.as_string())
        except:
            st.warning("E-mail riasztás sikertelen")

# API kulcsok
API_KEY = st.secrets.get("OILPRICEAPI_KEY")
NEWS_API_KEY = st.secrets.get("NEWSAPI_KEY")

# Brent adat lekérése
@st.cache_data(ttl=300)
def get_brent_data():
    if not API_KEY:
        st.warning("Nincs OilPriceAPI kulcs megadva")
        return pd.DataFrame({'date':[], 'price':[]})
    try:
        url = "https://api.oilpriceapi.com/v1/prices/historical"
        headers = {"Authorization": f"Token {API_KEY}"}
        params = {"by_code":"BRENT_USD","start":"2023-01-01","end":datetime.today().strftime('%Y-%m-%d')}
        resp = requests.get(url, headers=headers, params=params)
        data = pd.DataFrame(resp.json()['data'])
        data['date'] = pd.to_datetime(data['date'])
        data['price'] = data['price'].astype(float)
        return data.sort_values('date')
    except:
        st.warning("Olajár adat lekérés sikertelen")
        return pd.DataFrame({'date':[], 'price':[]})

df = get_brent_data()
st.subheader("Historikus Brent árak")

# Technikai indikátorok
if not df.empty:
    df['RSI'] = ta.rsi(df['price'], length=14)
    macd = ta.macd(df['price'])
    df['MACD'] = macd['MACD_12_26_9']
    bbands = ta.bbands(df['price'])
    df['Bollinger_upper'] = bbands['BBU_20_2.0']
    df['Bollinger_lower'] = bbands['BBL_20_2.0']

    buy_signals = df[(df['RSI'] < 30) | (df['price'] < df['Bollinger_lower'])]
    sell_signals = df[(df['RSI'] > 70) | (df['price'] > df['Bollinger_upper'])]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df['date'], df['price'], label='Price', color='blue')
    ax.scatter(buy_signals['date'], buy_signals['price'], label='Buy', marker='^', color='green', s=100)
    ax.scatter(sell_signals['date'], sell_signals['price'], label='Sell', marker='v', color='red', s=100)
    ax.set_title("Brent Ár + Buy/Sell jelzések")
    ax.set_xlabel("Dátum")
    ax.set_ylabel("USD")
    ax.legend()
    st.pyplot(fig)

# Hírek és sentiment
if NEWS_API_KEY:
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    try:
        news = newsapi.get_everything(q='Brent Oil OR Crude Oil', language='en', page_size=10)
        headlines = [article['title'] for article in news['articles']]
    except:
        st.warning("Hírek nem érhetők el")
        headlines = []
    st.subheader("Legfrissebb hírek")
    st.write(headlines)
    if headlines:
        sentiment_analyzer = pipeline("sentiment-analysis")
        news_sentiments = [sentiment_analyzer(h)[0]['label'] for h in headlines]
        sentiment_map = {'POSITIVE':1,'NEGATIVE':0,'NEUTRAL':0.5}
        df['news_sentiment'] = np.mean([sentiment_map.get(s,0.5) for s in news_sentiments])
    else:
        df['news_sentiment'] = 0.5
else:
    st.warning("Nincs NewsAPI kulcs megadva")
    df['news_sentiment'] = 0.5

# Buy/Sell jelzések és alert
if not df.empty:
    rsi_signal = "Hold"
    if df['RSI'].iloc[-1] < 30: rsi_signal = "Buy"
    elif df['RSI'].iloc[-1] > 70: rsi_signal = "Sell"

    macd_signal = "Hold"
    if df['MACD'].iloc[-1] > 0: macd_signal = "Buy"
    elif df['MACD'].iloc[-1] < 0: macd_signal = "Sell"

    bb_signal = "Hold"
    if df['price'].iloc[-1] < df['Bollinger_lower'].iloc[-1]: bb_signal = "Buy"
    elif df['price'].iloc[-1] > df['Bollinger_upper'].iloc[-1]: bb_signal = "Sell"

    signals = [rsi_signal, macd_signal, bb_signal]
    buy_count = signals.count("Buy")
    sell_count = signals.count("Sell")
    overall_signal = "Hold"
    if buy_count > sell_count: overall_signal = "Buy"
    elif sell_count > buy_count: overall_signal = "Sell"

    st.subheader("Buy/Sell jelzések")
    st.markdown(f"RSI: {rsi_signal} | MACD: {macd_signal} | Bollinger: {bb_signal}")
    st.markdown(f"Összesített jelzés: {overall_signal}")

    if overall_signal in ["Buy", "Sell"]:
        send_telegram_alert(f"Összesített Buy/Sell jelzés: {overall_signal}")
        send_email_alert("Brent Buy/Sell Jelzés", f"Összesített jelzés: {overall_signal}")

st.success(f"Dashboard frissítve (legutóbbi frissítés: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
