import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LinearRegression
import requests

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="Brent Dashboard Pro", layout="wide", page_icon="🛢️")

# CSS a stílusosabb megjelenéshez
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🛢️ Brent Olaj Dashboard & Trend Analízis")

# --- OLDALSÁV (BEÁLLÍTÁSOK) ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    period = st.selectbox("Időtartam", ["6mo", "1y", "2y", "5y"], index=1)
    
    st.divider()
    st.subheader("🤖 Telegram Bot")
    TELEGRAM_TOKEN = st.text_input("Bot Token", type="password", help="BotFather-től kapott token")
    TELEGRAM_CHAT_ID = st.text_input("Chat ID", help="A saját Chat ID-d")
    
    st.info("A botnak először küldj egy /start üzenetet!")

# --- ADATBETÖLTÉS ---
@st.cache_data(ttl=3600)
def load_data(period):
    data = yf.download("BZ=F", period=period, interval="1d")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

try:
    df = load_data(period).copy()

    # INDIKÁTOROK
    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain / loss)))

    # TREND ANALÍZIS
    def get_analysis(df):
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        if latest["RSI"] < 35: score += 1
        elif latest["RSI"] > 65: score -= 1
        if latest["Close"] > latest["EMA_20"]: score += 1
        else: score -= 1
        if latest["Close"] > prev["Close"]: score += 1
        else: score -= 1
        
        if score >= 2: return "ERŐS EMELKEDÉS (BULLISH)", "#2ecc71", score
        if score <= -2: return "ERŐS CSÖKKENÉS (BEARISH)", "#e74c3c", score
        return "OLDALAZÁS / BIZONYTALAN", "#bdc3c7", score

    signal_text, signal_color, score = get_analysis(df)

    # --- FŐ METRIKÁK ---
    m1, m2, m3, m4 = st.columns(4)
    current_price = float(df['Close'].iloc[-1])
    diff = current_price - float(df['Close'].iloc[-2])
    
    m1.metric("Aktuális Ár", f"${current_price:.2f}", f"{diff:.2f}")
    m2.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.1f}")
    m3.metric("Trend Pontszám", score)
    m4.write(f"**Státusz:** <br> <span style='color:{signal_color}; font-weight:bold; font-size:20px;'>{signal_text}</span>", unsafe_allow_html=True)

    # --- INTERAKTÍV PLOTLY GRAFIKON ---
    st.subheader("📊 Árfolyam és Indikátorok")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])

    # Gyertyadiagram vagy vonaldiagram
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Brent Close', line=dict(color='#3498db', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='#f1c40f', width=1, dash='dash')), row=1, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='#9b59b6')), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    fig.update_layout(height=600, template="plotly_white", hovermode="x unified", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- ELŐREJELZÉS ---
    st.divider()
    col_pre_1, col_pre_2 = st.columns([2, 1])
    
    with col_pre_1:
        st.subheader("🔮 5 Napos Lineáris Trend")
        df_p = df.dropna().copy()
        df_p["t"] = np.arange(len(df_p))
        
        model = LinearRegression().fit(df_p[["t"]], df_p["Close"])
        future_t = np.arange(len(df_p), len(df_p) + 5).reshape(-1, 1)
        future_preds = model.predict(future_t)
        
        # Plotly előrejelzés grafikon
        fig_pred = go.Figure()
        fig_pred.add_trace(go.Scatter(x=df_p.index[-30:], y=df_p['Close'].iloc[-30:], name="Múltbeli", line=dict(color="#34495e")))
        
        future_dates = [df_p.index[-1] + pd.Timedelta(days=i) for i in range(1, 6)]
        fig_pred.add_trace(go.Scatter(x=future_dates, y=future_preds, name="Becsült", line=dict(color="#e74c3c", dash="dot")))
        
        fig_pred.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), template="plotly_white")
        st.plotly_chart(fig_pred, use_container_width=True)

    with col_pre_2:
        st.subheader("🚨 Akciók")
        if st.button("Küldés Telegramra", use_container_width=True):
            if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
                msg = f"🛢️ Brent Olaj Jelzés\n\nIrány: {signal_text}\nÁr: ${current_price:.2f}\nRSI: {df['RSI'].iloc[-1]:.1f}\nPontszám: {score}"
                url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
                try:
                    res = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
                    if res.status_code == 200: st.success("Üzenet elküldve!")
                    else: st.error("Hiba a küldés során.")
                except: st.error("Kapcsolódási hiba.")
            else:
                st.warning("Hiányzó Telegram adatok az oldalsávban!")
        
        st.info(f"**Elemzés:** {'Vételi erő látszik' if score > 0 else 'Eladói nyomás dominál'}. A lineáris modell alapján az irány {'felfelé' if future_preds[-1] > current_price else 'lefelé'} mutat.")

except Exception as e:
    st.error(f"Hiba történt: {e}")

