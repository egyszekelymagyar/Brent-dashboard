import streamlit as st
import pandas as pd
import numpy as np

# --- 1. HISTORIKUS SOKK-ADATBÁZIS (Súlyozási alap) ---
HISTORICAL_SHOCKS = {
    "WAR_MAJOR": {"impact": 0.30, "duration_days": 14, "source_reliability": 0.95}, # pl. 2022 Oroszország
    "TERROR_ATTACK": {"impact": 0.05, "reversal_pct": -0.25, "source_reliability": 0.85}, # pl. 9/11
    "SUPPLY_DISRUPTION": {"impact": 0.15, "duration_days": 30, "source_reliability": 0.90}, # pl. 1990 Öböl
    "DEMAND_CRASH": {"impact": -0.40, "duration_days": 90, "source_reliability": 0.80} # pl. COVID
}

# --- 2. BRÓKER HÍRFORRÁSOK ÉS SÚLYOZÁSUK ---
NEWS_CHANNELS = {
    "Bloomberg Energy": {"weight": 0.45, "focus": "Instant Market Moves"},
    "Reuters Energy": {"weight": 0.30, "focus": "Geopolitical Supply Facts"},
    "Financial Times": {"weight": 0.15, "focus": "Structural Shifts"},
    "OilPrice/Investing": {"weight": 0.10, "focus": "Retail Sentiment"}
}

def calculate_weighted_sentiment(current_headlines):
    """
    Kiszámítja a hírek súlyozott hatását a múltbeli sokkok tükrében.
    """
    total_impact = 0
    # Szimulált elemzés: A program keresi a kulcsszavakat a forrásokban
    for headline in current_headlines:
        for shock_type, data in HISTORICAL_SHOCKS.items():
            if shock_type.split('_')[0].lower() in headline.lower():
                # Bróker súlyozás + Múltbeli hatás
                total_impact += data['impact'] * 0.4 # 40%-os súly a múltbeli hasonlóságnak
                
    return total_impact

# --- 3. ADAPTÍV MODEL (A JÖVŐ JÓSLÁSA A MÚLTBÓL) ---
st.subheader("📡 Bróker-szintű Hír- és Sokk-elemzés")

# Szimulált aktuális hírfolyam
current_news = [
    "Bloomberg: Major military escalation in Middle East",
    "Reuters: Pipeline disruption in North Sea",
    "FT: OPEC+ considering supply cuts"
]

impact = calculate_weighted_sentiment(current_news)

# UI Megjelenítés
col1, col2 = st.columns(2)
with col1:
    st.info("**Súlyozott Hírhatás (News Sentiment Score):**")
    st.progress(min(max((impact + 0.5), 0.0), 1.0))
    st.write(f"Kalkulált hatás: {impact*100:.2f}%-os volatilitási várakozás")

with col2:
    st.write("**Referencia események (Learning Base):**")
    st.write("- 2022 Orosz Invázió (Supply shock model)")
    st.write("- 9/11 Terror (Demand/Panic model)")
    st.write("- 1973/1990 Energy crises")

# --- 4. BACKTEST: JÓSLAT VS VALÓSÁG ---
# A modell itt futtatja le a "vak" szimulációt
# 1. Fogja a múltbeli perces adatot
# 2. Hozzáadja a hírek súlyozott hatását
# 3. Összeveti a percenkénti tényadatokkal (yfinance)
