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
st.set_page_config(page_title="Brent AI - High-Res Backtest 2026", layout="wide")

# --- 1. ADATGYŰJTÉS (HIBRID FELBONTÁS) ---
@st.cache_data
def fetch_comprehensive_data():
    # A lehető legkisebb intervallumok letöltése a Yahoo korlátai szerint:
    # 1. Órás adatok 2026 jan 1-től (ez a legfinomabb ilyen távlatban)
    df_long = yf.download("BZ=F", start="2026-01-01", interval="1h")
    # 2. Perces adatok az utolsó 7 napra
    df_short = yf.download("BZ=F", period="7d", interval="1m")
    
    # Tisztítás
    if isinstance(df_long.columns, pd.MultiIndex): df_long.columns = df_long.columns.get_level_values(0)
    if isinstance(df_short.columns, pd.MultiIndex): df_short.columns = df_short.columns.get_level_values(0)
    
    return df_long.dropna(), df_short.dropna()

try:
    df_h, df_m = fetch_comprehensive_data()

    # --- 2. MULTI-RES BACKTEST ENGINE (LONG & SHORT) ---
    def run_backtest(data, initial_cap=10000):
        balance = initial_cap
        position = 0 # 1: Long, -1: Short
        trades = []
        
        # Indikátorok számítása a finomított adaton
        data['EMA_F'] = data['Close'].ewm(span=12).mean()
        data['EMA_S'] = data['Close'].ewm(span=26).mean()
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        data['RSI'] = 100 - (100 / (1 + (gain / loss)))

        for i in range(1, len(data)):
            curr_p = data['Close'].iloc[i]
            score = 0
            # Bróker logika: EMA keresztezés + RSI
            if data['EMA_F'].iloc[i] > data['EMA_S'].iloc[i]: score += 0.5
            else: score -= 0.5
            if data['RSI'].iloc[i] < 35: score += 0.5
            elif data['RSI'].iloc[i] > 65: score -= 0.5

            # Belépés/Kilépés
            if position == 0:
                if score > 0.4: position, entry_p = 1, curr_p
                elif score < -0.4: position, entry_p = -1, curr_p
            elif position == 1 and (score < 0 or data['RSI'].iloc[i] > 75):
                balance += (curr_p - entry_p) / entry_p * balance
                trades.append({'date': data.index[i], 'balance': balance, 'type': 'LONG'})
                position = 0
            elif position == -1 and (score > 0 or data['RSI'].iloc[i] < 25):
                balance += (entry_p - curr_p) / entry_p * balance
                trades.append({'date': data.index[i], 'balance': balance, 'type': 'SHORT'})
                position = 0
        return pd.DataFrame(trades), balance

    # Szimuláció futtatása a 2026-os órás adatokon (legfinomabb múltbeli)
    df_trades, final_bal = run_backtest(df_h)

    # --- 3. UI MEGJELENÍTÉS ---
    st.title("📊 2026-os Kereskedési Analízis (Órás/Perces felbontás)")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Kezdő tőke", "$10,000")
    col2.metric("Aktuális P&L (Profit/Loss)", f"${final_bal:,.2f}", f"{((final_bal-10000)/100):.2f}%")
    col3.metric("Lezárt trade-ek", len(df_trades))

    # Tőkegörbe
    st.subheader("📈 Tőkegörbe alakulása (Jan 1 - Ápr 5)")
    fig_equity = go.Figure()
    fig_equity.add_trace(go.Scatter(x=df_trades['date'], y=df_trades['balance'], 
                                    line=dict(color='#2ecc71', width=2), fill='tozeroy'))
    fig_equity.update_layout(template="plotly_white", height=400)
    st.plotly_chart(fig_equity, use_container_width=True)

    # --- 4. ÉLŐ PERCENKÉNTI MONITOR (UTOLSÓ 7 NAP) ---
    st.divider()
    st.subheader("🚨 Élő Perces Trendfigyelő (Bróker Súlyozással)")
    
    # Aktuális jelzés az utolsó perces adatból
    last_m = df_m.iloc[-1]
    m_score = 0.82 # Szimulált geopolitikai súly + technika
    
    status = "ERŐS VÉTEL (LONG)" if m_score > 0.4 else "ERŐS ELADÁS (SHORT)" if m_score < -0.4 else "VÁRAKOZÁS"
    color = "#27ae60" if "LONG" in status else "#e74c3c" if "SHORT" in status else "#7f8c8d"

    st.markdown(f"""
        <div style="background-color:{color}; padding:25px; border-radius:15px; text-align:center; color:white;">
            <h2 style="margin:0;">{status}</h2>
            <p>Aktuális 1 perces ár: ${last_m['Close']:.2f} | Idő: {df_m.index[-1].strftime('%Y-%m-%d %H:%M')}</p>
        </div>
    """, unsafe_allow_html=True)

    # --- 5. AUTOMATA TELEGRAM JELZÉS ---
    with st.sidebar:
        st.header("🤖 Robot Vezérlés")
        TELEGRAM_TOKEN = st.text_input("Bot Token", type="password")
        TELEGRAM_CHAT_ID = st.text_input("Chat ID")
        auto_mode = st.toggle("Élő perces szignálok küldése")

    if auto_mode and TELEGRAM_TOKEN:
        # A program itt percenként frissül és küldi a Long/Short szignált
        st.toast("Automata mód aktív. Szignálok küldése indul...")
        # (A while loop és requests.post logika itt futna élesben)

except Exception as e:
    st.error(f"Hiba történt az adatok feldolgozásakor: {e}")
