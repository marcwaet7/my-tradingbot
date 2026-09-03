import streamlit as st
import datetime, json, os, time, pandas as pd, requests, yfinance as yf, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =====================================================================
# 1. INITIALISEER HET GEHEUGEN DIRECT (VOORKOM KEYERROR)
# =====================================================================
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = []

# =====================================================================
# 2. CLOUD CONFIGURATIE & SECRETS
# =====================================================================
COOLDOWN_PERIOD = datetime.timedelta(minutes=15)
COOLDOWN_FILE = "cooldown_register.json"
TRANSACTIE_FILE = "transacties.json"

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

custom_session = requests.Session()
custom_session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

# =====================================================================
# 3. HULPFUNCTIES & HISTORIE
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

def bereken_atr_limieten(data):
    h, l, cp = data['High'], data['Low'], data['Close'].shift(1)
    tr = (h - l).combine((h - cp).abs(), max).combine((l - cp).abs(), max)
    atr = tr.rolling(window=14).mean().iloc[-1]
    px = float(data['Close'].iloc[-1])
    return round(px, 2), round(px - (atr * 1.5), 2), round(px + (atr * 3.0), 2)

def bereken_rsi(series):
    delta = series.diff()
    g = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    l = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    return 100 - (100 / (1 + (g / l)))

def bereken_macd(series):
    macd = series.ewm(span=12, adjust=False).mean() - series.ewm(span=26, adjust=False).mean()
    return macd, macd.ewm(span=9, adjust=False).mean()

# =====================================================================
# 4. LIVE SCANNER EN TRANS-ACTIE LOOP
# =====================================================================
reg = laad_cooldown_register()
totaal_pnl = 0.0
overblijvers = []
belgische_tijd_str = (datetime.datetime.now() + datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')

# Bereken live PnL voor eventuele openstaande posities
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
                sla_transactie_op(belgische_tijd_str, p["ticker"], p["direction"], pnl)
                continue
        overblijvers.append(p)
    except Exception:
        overblijvers.append(p)

st.session_state["portfolio"] = overblijvers

# MAP SCANNER (5M INTERVALLEN)
for ticker in laad_universe():
    try:
        if not mag_nieuwe_positie_openen(ticker, st.session_state["portfolio"], reg): continue
        df = yf.Ticker(ticker, session=custom_session).history(period="1d", interval="5m")
        if len(df) < 35: continue
        
        df['RSI'] = bereken_rsi(df['Close'])
        macd, sig = bereken_macd(df['Close'])
        
        # Strenge RSI < 45 + MACD Crossover Filter
        if df['RSI'].iloc[-1] < 45 and macd.iloc[-2] <= sig.iloc[-2] and macd.iloc[-1] > sig.iloc[-1]:
            px, sl, tp = bereken_atr_limieten(df)
            st.session_state["portfolio"].append({"ticker": ticker, "direction": "LONG", "entry_price": px, "stop_loss": sl, "take_profit": tp, "shares": 14})
    except Exception: pass

# =====================================================================
# 5. VISUEEL DASHBOARD & LAY-OUT
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
    st.info("Wacht op actieve trades van de 5m Scalper... Het scherm ververst live.")

st.markdown("---")
st.subheader("📜 Gesloten Transacties (Dagelijkse Trades)")
gesloten_lijst = laad_transacties()

if len(gesloten_lijst) > 0:
    st.dataframe(pd.DataFrame(gesloten_lijst).iloc[::-1])
else:
    st.info("Net gestart. Gesloten trades verschijnen hier automatisch zodra ze hun SL of TP raken.")

# Automatische onzichtbare verversing elke 30 seconden via de gsm-vriendelijke timer
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=30000, key="bot_refresh")
