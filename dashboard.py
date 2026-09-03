import streamlit as st
import datetime, json, os, time, pandas as pd, requests, yfinance as yf, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =====================================================================
# 1. CLOUD CONFIGURATIE & SECRETS (MET VEILIGE FALLBACK)
# =====================================================================
COOLDOWN_PERIOD = datetime.timedelta(minutes=15)
COOLDOWN_FILE = "cooldown_register.json"

# Probeer eerst de Streamlit Cloud Secrets te laden, anders laden we lokaal via .env
try:
    EMAIL_ZENDER = st.secrets.get("EMAIL_ZENDER", os.getenv("EMAIL_ZENDER", ""))
    EMAIL_WACHTWOORD = st.secrets.get("EMAIL_WACHTWOORD", os.getenv("EMAIL_WACHTWOORD", ""))
    EMAIL_ONTVANGER = st.secrets.get("EMAIL_ONTVANGER", os.getenv("EMAIL_ONTVANGER", ""))
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    EMAIL_ZENDER = os.getenv("EMAIL_ZENDER", "")
    EMAIL_WACHTWOORD = os.getenv("EMAIL_WACHTWOORD", "")
    EMAIL_ONTVANGER = os.getenv("EMAIL_ONTVANGER", "")


# =====================================================================
# 2. HULPFUNCTIES & HISTORIE
# =====================================================================
def laad_transacties():
    if not os.path.exists(TRANSACTIE_FILE): return []
    try:
        with open(TRANSACTIE_FILE, "r") as f: return json.load(f)
    except Exception: return []

def sla_transactie_op(tijdstip, ticker, richting, pnl):
    historie = laad_transacties()
    historie.append({
        "Tijdstip (BE)": tijdstip,
        "Ticker": ticker.upper(),
        "Richting": richting,
        "Resultaat (PnL)": f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
    })
    try:
        with open(TRANSACTIE_FILE, "w") as f: json.dump(historie, f, indent=4)
    except Exception: pass

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
belgische_tijd_str = (datetime.datetime.now() + datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')

for p in st.session_state["portfolio"]:
    try:
        df = yf.Ticker(p["ticker"], session=custom_session).history(period="1d", interval="1m")
        if not df.empty:
            px = float(df["Close"].iloc[-1])
            pnl = (px - p["entry_price"]) * p["shares"]
            totaal_pnl += pnl
            
            if px <= p["stop_loss"] or px >= p["take_profit"]:
                reg[p["ticker"].upper()] = datetime.datetime.now() + COOLDOWN_PERIOD
                sla_cooldown_register_op(reg)
                # Sla de trade permanent op in het dagelijkse logboek
                sla_transactie_op(belgische_tijd_str, p["ticker"], p["direction"], pnl)
                continue
        overblijvers.append(p)
    except Exception:
        overblijvers.append(p)

st.session_state["portfolio"] = overblijvers

# =====================================================================
# 4. VISUEEL DASHBOARD & LAY-OUT
# =====================================================================
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
    df_visueel = pd.DataFrame(st.session_state["portfolio"])
    st.dataframe(df_visueel[['ticker', 'direction', 'entry_price', 'stop_loss', 'take_profit', 'shares']])
else:
    st.info("Wacht op actieve trades van de 5m Scalper...")

# --- DE NIEUWE DIENST: GESLOTEN TRANSACTIES LOGBOEK ---
st.markdown("---")
st.subheader("📜 Gesloten Transacties (Dagelijkse Trades)")
gesloten_lijst = laad_transacties()

if len(gesloten_lijst) > 0:
    df_gesloten = pd.DataFrame(gesloten_lijst)
    # Toon de nieuwste transacties altijd bovenaan
    st.dataframe(df_gesloten.iloc[::-1])
else:
    st.info("Net gestart. Gesloten trades verschijnen hier automatisch zodra ze hun SL of TP raken.")
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=30000, key="bot_refresh")


