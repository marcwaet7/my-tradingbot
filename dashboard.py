import streamlit as st
import subprocess
import os

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
        st.error(f"⚠️ Kon achtergrondbot ikke starten: {e}")

# =====================================================================
# VISUEEL DASHBOARD
# =====================================================================
st.title("📈 Live RSI + MACD Trading Dashboard")
st.write("De bot scant momenteel de 5-minutengrafiek van je universe op de achtergrond.")

# Hieronder worden je tabellen geladen
st.subheader("💼 Actieve Portfolio")
st.info("Wacht op actieve trades van de 5m Scalper...")
