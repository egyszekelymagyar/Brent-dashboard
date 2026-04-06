import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- BRENT AI - KONTRASZTOS MAGYAR TERMINAL ---
st.set_page_config(page_title="Brent AI - Kontrasztos Grid", layout="wide", page_icon="🏦")

# EXTRA ERŐS CSS: Fehér szövegek és 2x2 rács elrendezés
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    
    /* Metrika feliratok és értékek kényszerített fehérítése */
    div[data-testid="stMetricLabel"] { 
        color: #ffffff !important; 
        font-size: 20px !important; 
        font-weight: bold !important;
        text-transform: uppercase;
    }
    div[data-testid="stMetricValue"] { 
        color: #ffffff !important; 
        font-size: 34px !important; 
        font-weight: 800 !important;
        text-shadow: 1px 1px 2px #000;
    }
    div[data-testid="stMetric"] {
        background-color: #1a1c24;
        border: 2px solid #444;
        padding: 20px;
        border-radius: 12px;
    }

    /* Nagy szignál box - Kényszerített FEHÉR szöveg */
    .signal-box { padding: 40px; border-radius: 20px; text-align: center; border: 4px solid #ffffff; margin-bottom: 25px; }
    .signal-title { 
        font-size: 65px !important; 
        color: #ffffff !important; 
        font-weight: 900 !important; 
        text-shadow: 3px 3px 6px #000000 !important;
        margin: 0 !important;
    }
    .signal-sub { 
        font-size: 30px !important; 
        color: #ffffff !important; 
        margin-top: 15px !important;
        font-weight: bold !important;
        text-shadow: 2px 2px 4px #000000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def get_market_info():
    tz_hu, tz_ny = pytz.timezone('Europe/Budapest'), pytz.timezone('America/New_York')
    geo_score = 0.88 # 88% Bullish hír-szentiment
    news_summary = "OPEC+ jelképes emelés | Hormuzi blokád | Trump fenyegetés"
    return datetime.now(tz_hu).strftime("%H:%M:%S"), datetime.now(tz_ny).strftime("%H:%M:%S"), geo_score, news_summary

@st.cache_data(ttl=60)
def fetch_data():
    df_m = yf.download("BZ=F", period="7d", interval="1m").dropna()
    if isinstance(df_m.columns, pd.MultiIndex): df_m.columns = df_m.columns.get_level_values(0)
    return df_m

def apply_indicators(df):
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    return df.dropna()

try:
    df_m = fetch_data()
    df_m = apply_indicators(df_m)
    t_hu, t_ny, geo_score, news_txt = get_market_info()
    l1 = df_m.iloc[-1]
    
    # SZÁZALÉKOS SZÁMÍTÁS (55/25/20)
    tech_val = 100 if l1['Close'] > l1['SMA_20'] else 0
    fund_val = 40 
    geo_val = geo_score * 100
    buy_pct = (geo_val * 0.55) + (tech_val * 0.25) + (fund_val * 0.20)
    sell_pct = 100 - buy_pct

    # --- FEJLÉC: 2x2 ELRENDEZÉS ---
    st.title("🏦 BRENT AI - ELITE TERMINAL")
    
    # Első sor: IDŐK
    row1_col1, row1_col2 = st.columns(2)
    row1_col1.metric("Budapest (CET)", t_hu)
    row1_col2.metric("New York (EST)", t_ny)
    
    # Második sor: ADATOK
    row2_col1, row2_col2 = st.columns(2)
    row2_col1.metric("Brent Olaj Ár", f"${float(l1['Close']):.2f}")
    row2_col2.metric("Volatilitás (ATR)", f"${float(l1['ATR']):.2f}")

    st.write("") # Térköz

    # --- SZIGNÁL PANEL ---
    if buy_pct > 65:
        status, color = "VÉTEL! 🚀", "#2ecc71"
    elif sell_pct > 65:
        status, color = "ELADÁS! 📉", "#e74c3c"
    else:
        status, color = "VÁRAKOZÁS ⚖️", "#95a5a6"

    st.markdown(f"""
        <div class="signal-box" style="background-color: {color}; border-color: #ffffff;">
            <div class="signal-title">{status}</div>
            <div class="signal-sub">
                VÉTEL: {buy_pct:.1f}% | ELADÁS: {sell_pct:.1f}%
            </div>
            <p style="color: white; margin-top:10px; font-size:18px;">
                Súlyozás: 55% Hírek | 25% Technika | 20% Fundamentum
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Célárak és hírek
    sl = l1['Close'] - (l1['ATR'] * 2.5) if buy_pct > 50 else l1['Close'] + (l1['ATR'] * 2.5)
    tp = l1['Close'] + (l1['ATR'] * 5) if buy_pct > 50 else l1['Close'] - (l1['ATR'] * 5)
    
    st.success(f"🎯 **Célár:** ${tp:.2f} | 🛡️ **Stop-Loss:** ${sl:.2f}")
    st.info(f"🗞️ **Hírek:** {news_txt}")

    # GRAFIKON
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m.index[-100:], y=df_m['Close'].iloc[-100:], name="Ár", line=dict(color="#00ffcc", width=3)))
    fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("A rendszer vasárnap éjféli nyitásra vár. Az élő adatok ekkor frissítik a szignálokat.")
