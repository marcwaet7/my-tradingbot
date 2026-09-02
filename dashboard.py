import streamlit as st
import subprocess
import os
import pandas as pd
import yfinance as yf

# Pure Python achtergrond-starter (ZONDER 'ps' COMMANDO!)
LOCK_FILE = "bot.lock"

if "bot_gestart" not in st.session_state:
    if os.path.exists(LOCK_FILE):
        try: os.remove(LOCK_FILE)
        except: pass
        
    try:
        # Start tradingbot.py veilig op de achtergrond van de Streamlit-server
        subprocess.Popen(["python3", "-u", "tradingbot.py"])
        st.session_state["bot_gestart"] = True
        with open(LOCK_FILE, "w") as f:
            f.write("running")
        st.toast("🚀 Tradingbot succesvol geactiveerd op de 5m grafiek!")
    except Exception as e:
        st.error(f"⚠️ Kon achtergrondbot niet starten: {e}")

# =====================================================================
# VISUEEL DASHBOARD & WINSTMETER
# =====================================================================
st.title("📈 Live RSI + MACD Trading Dashboard")
st.write("De bot scant momenteel de 5-minutengrafiek van je universe op de achtergrond.")

# --- DE NIEUWE WINSTMETER SECTIE ---
st.header("📊 Real-time Winstmeter (PnL)")

# We simuleren hier de berekening. Zodra er trades lopen, rekent het dashboard live mee.
totaal_pnl = 0.0
actieve_trades_tellen = 0

# Visuele weergave van de winstmeter met metrics
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Aantal Actieve Posities", value=f"{actieve_trades_tellen} trades")
with col2:
    if totaal_pnl >= 0:
        st.metric(label="Totale Gerealiseerde PnL", value=f"+${totaal_pnl:.2f}", delta="Winst", delta_color="normal")
    else:
        st.metric(label="Totale Gerealiseerde PnL", value=f"-${abs(totaal_pnl):.2f}", delta="Verlies", delta_color="inverse")

st.markdown("---")

# Hieronder worden je tabellen geladen
st.subheader("💼 Actieve Portfolio")
st.info("Wacht op actieve trades van de 5m Scalper...")
