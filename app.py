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
st.title("⛽ Brent Olaj Élő Előrejelző Dashboard")

# Sidebar beállítások
st.sidebar.header("⚠️ Riasztási beállítások")
price_thresh = st.sidebar.slider("Árváltozás küszöb (%)", 0.5, 10.0, 2.0, 0.1)/100
sentiment_thresh = st.sidebar.slider("Sentiment változás küszöb", 0.1, 1.0, 0.3, 0.05)

# Telegram
BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})

# E-mail
EMAIL_USER = st.secrets["EMAIL_USER"]
EMAIL_PASS = st.secrets["EMAIL_PASS"]
TO_EMAIL = st.secrets["TO_EMAIL"]
def send_email_alert(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = TO_EMAIL
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, TO_EMAIL, msg.as_string())

# API kulcsok
API_KEY = st.secrets["OILPRICEAPI_KEY"]
NEWS_API_KEY = st.secrets["NEWSAPI_KEY"]

# Brent adat
@st.cache_data(ttl=300)
def get_brent_data():
    url = "https://api.oilpriceapi.com/v1/prices/historical"
    headers = {"Authorization": f"Token {API_KEY}"}
    params = {"by_code":"BRENT_USD","start":"2023-01-01","end":datetime.today().strftime('%Y-%m-%d')}
    resp = requests.get(url, headers=headers, params=params)
    data = pd.DataFrame(resp.json()['data'])
    data['date'] = pd.to_datetime(data['date'])
    data['price'] = data['price'].astype(float)
    return data.sort_values('date')

df = get_brent_data()
st.subheader("📈 Historikus Brent árak")

# Technikai indikátorok
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
newsapi = NewsApiClient(api_key=NEWS_API_KEY)
news = newsapi.get_everything(q='Brent Oil OR Crude Oil', language='en', page_size=10)
headlines = [article['title'] for article in news['articles']]
st.subheader("📰 Legfrissebb hírek")
st.write(headlines)

sentiment_analyzer = pipeline("sentiment-analysis")
news_sentiments = [sentiment_analyzer(h)[0]['label'] for h in headlines]
sentiment_map = {'POSITIVE':1,'NEGATIVE':0,'NEUTRAL':0.5}
df['news_sentiment'] = np.mean([sentiment_map.get(s,0.5) for s in news_sentiments])

# LSTM előrejelzés
features = ['price','RSI','MACD','Bollinger_upper','Bollinger_lower','news_sentiment']
data_values = df[features].fillna(method='bfill').values
scaler = MinMaxScaler()
scaled = scaler.fit_transform(data_values)

def make_dataset(data, window=20):
    X, y = [], []
    for i in range(len(data)-window):
        X.append(data[i:i+window])
        y.append(data[i+window,0])
    return np.array(X), np.array(y)

window = 20
X, y = make_dataset(scaled, window)
X = X.reshape((X.shape[0], X.shape[1], len(features)))

model = Sequential([LSTM(64,input_shape=(X.shape[1],X.shape[2])), Dense(1)])
model.compile(optimizer='adam', loss='mse')
model.fit(X, y, epochs=20, batch_size=16, verbose=0)

last_data = scaled[-window:].reshape(1, window, len(features))
preds = []
for _ in range(7):
    pred = model.predict(last_data)
    next_input = last_data[:,1:,:]
    next_feature_row = np.zeros((1,1,len(features)))
    next_feature_row[0,0,0] = pred
    next_feature_row[0,0,1:] = last_data[0,-1,1:]
    last_data = np.concatenate([next_input, next_feature_row], axis=1)
    preds.append(pred[0,0])

preds_prices = scaler.inverse_transform(np.concatenate([np.array(preds).reshape(-1,1), 
                                                       np.tile(last_data[0,-1,1:], (7,1))], axis=1))[:,0]
st.subheader("🔮 Előrejelzés a következő 7 napra")
st.line_chart(pd.DataFrame({'Predicted Price': preds_prices}, index=pd.date_range(df['date'].max(), periods=7, closed='right')))

# Riasztások
if len(df) > 1:
    price_change = (df['price'].iloc[-1] - df['price'].iloc[-2]) / df['price'].iloc[-2]
    if abs(price_change) > price_thresh:
        alert_msg = f"⚠️ Ár változás jelentős: {price_change*100:.2f}%"
        st.warning(alert_msg)
        send_telegram_alert(alert_msg)
        send_email_alert("⚠️ Brent Árriasztás", alert_msg)

    sentiment_change = df['news_sentiment'].iloc[-1] - df['news_sentiment'].iloc[-2]
    if abs(sentiment_change) > sentiment_thresh:
        alert_msg = f"📰 Hírsentiment jelentősen változott: {sentiment_change:.2f}"
        st.warning(alert_msg)
        send_telegram_alert(alert_msg)
        send_email_alert("📰 Brent Hírsentiment Riasztás", alert_msg)

# Buy/Sell összesített jelzés
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

st.subheader("💹 Buy/Sell jelzések")
st.markdown(f"**RSI:** {rsi_signal} | **MACD:** {macd_signal} | **Bollinger:** {bb_signal}")
st.markdown(f"**Összesített jelzés:** {overall_signal}")

if overall_signal in ["Buy", "Sell"]:
    send_telegram_alert(f"💹 Összesített Buy/Sell jelzés: {overall_signal}")
    send_email_alert("💹 Brent Buy/Sell Jelzés", f"Összesített jelzés: {overall_signal}")

st.success(f"Dashboard frissítve ✅ (legutóbbi frissítés: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
