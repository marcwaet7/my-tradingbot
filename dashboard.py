import streamlit as st
import datetime, json, os, time, pandas as pd, requests, yfinance as yf, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =====================================================================
# 1. CLOUD CONFIGURATIE & SECRETS
# =====================================================================
COOLDOWN_PERIOD = datetime.timedelta(minutes=15)
COOLDOWN_FILE = "cooldown_register.json"

EMAIL_ZENDER = st.secrets.get("EMAIL_ZENDER", "")
EMAIL_WACHTWOORD = st.secrets.get("EMAIL_WACHTWOORD", "")
EMAIL_ONTVANGER = st.secrets.get("EMAIL_ONTVANGER", "")

custom_session = requests.Session()
custom_session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

# HARDCODED START-TRADES DIE ALTIJD BLIJVEN STAAN VOOR HET DASHBOARD
if "portfolio" not in st.session_state or len(st.session_state["portfolio"]) == 0:
    st.session_state["portfolio"] = [
        {"ticker": "AAPL", "direction": "LONG", "entry_price": 175.50, "stop_loss": 170.00, "take_profit": 230.00, "shares": 14},
        {"ticker": "TSLA", "direction": "LONG", "entry_price": 240.20, "stop_loss": 210.00, "take_profit": 310.00, "shares": 14}
    ]

# =====================================================================
# 2. HULPFUNCTIES
# =====================================================================
def laad_cooldown_register():
    if not os.path.exists(COOLDOWN_FILE): return {}
    try:
        with open(COOLDOWN_FILE, "r") as f: data = json.load(f)
        nu = datetime.datetime.now()
        return {t: datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S") for t, s in data.items() if datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S") > nu}
    except Exception: return {}

def sla_cooldown_register_op(reg):
    try:
        with open(COOLDOWN_FILE, "w") as f: json.dump({t: d.strftime("%Y-%m-%d %H:%M:%S") for t, d in reg.items()}, f, indent=4)
    except Exception: pass

def laad_universe():
    return ["PLTR", "AMZN", "NFLX", "GOOGL", "AAPL", "MSFT", "TSLA", "NVDA", "META", "MARA"]

def mag_nieuwe_positie_openen(ticker, portfolio, reg):
    if any(p["ticker"].upper() == ticker.upper() for p in portfolio): return False
    if ticker.upper() in reg and datetime.datetime.now() < reg[ticker.upper()]: return False
    return True

# =====================================================================
# 3. LIVE SCANNER EN TRANS-ACTIE LOOP
# =====================================================================
reg = laad_cooldown_register()
totaal_pnl = 0.0
overblijvers = []

# Real-time portfolio controle en live PnL berekening
for p in st.session_state["portfolio"]:
    try:
        df = yf.Ticker(p["ticker"], session=custom_session).history(period="1d", interval="1m")
        if not df.empty:
            px = float(df["Close"].iloc[-1])
            pnl = (px - p["entry_price"]) * p["shares"]
            totaal_pnl += pnl
            
            # Controleer of SL of TP is geraakt
            if px <= p["stop_loss"] or px >= p["take_profit"]:
                reg[p["ticker"].upper()] = datetime.datetime.now() + COOLDOWN_PERIOD
                sla_cooldown_register_op(reg)
                continue # Verwijder uit portfolio
        overblijvers.append(p)
    except Exception:
        overblijvers.append(p)

st.session_state["portfolio"] = overblijvers

# =====================================================================
# 4. VISUEEL DASHBOARD & LAY-OUT
# =====================================================================
# Bereken de Belgische tijdzone (Cloud tijd + 2 uur zomertijd)
belgische_tijd = datetime.datetime.now() + datetime.timedelta(hours=2)

st.title("📈 Live RSI + MACD Trading Dashboard")
st.write(f"Laatste scan succesvol afgerond om: {belgische_tijd.strftime('%H:%M:%S')}")

st.header("📊 Real-time Winstmeter (PnL)")
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Aantal Actieve Posities", value=f"{len(st.session_state['portfolio'])} trades")
with col2:
    if totaal_pnl >= 0:
        st.metric(label="Totale Live PnL", value=f"+${totaal_pnl:.2f}", delta="Winst")
    else:
        st.metric(label="Totale Live PnL", value=f"-${abs(totaal_pnl):.2f}", delta="Verlies", delta_color="inverse")

st.markdown("---")
st.subheader("💼 Actieve Portfolio")

if len(st.session_state["portfolio"]) > 0:
    # Maak er een mooie, leesbare tabel van voor je telefoon
    df_visueel = pd.DataFrame(st.session_state["portfolio"])
    st.dataframe(df_visueel[['ticker', 'direction', 'entry_price', 'stop_loss', 'take_profit', 'shares']])
else:
    st.info("Wacht op actieve trades van de 5m Scalper... De pagina ververst live.")

# Automatische pagina-refresh elke 30 seconden
time.sleep(30)
st.rerun()
