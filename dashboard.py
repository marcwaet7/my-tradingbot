import streamlit as st
import datetime, json, os, time, pandas as pd, requests, yfinance as yf, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =====================================================================
# 1. CLOUD CONFIGURATIE & SECRETS
# =====================================================================
COOLDOWN_PERIOD = datetime.timedelta(minutes=15)
COOLDOWN_FILE = "cooldown_register.json"

# Haal de geheime e-mailgegevens veilig op uit de Streamlit Secrets
EMAIL_ZENDER = st.secrets.get("EMAIL_ZENDER", "")
EMAIL_WACHTWOORD = st.secrets.get("EMAIL_WACHTWOORD", "")
EMAIL_ONTVANGER = st.secrets.get("EMAIL_ONTVANGER", "")

custom_session = requests.Session()
custom_session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

# INITIALISEER HET PORTFOLIO IN HET GEHEUGEN VAN DE CLOUD
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = []

# =====================================================================
# 2. REKENKERNEN & RECHTEN
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

def stuur_trade_email(ticker, px, sl, tp):
    if not EMAIL_ZENDER or not EMAIL_WACHTWOORD: return
    msg = MIMEMultipart()
    msg['From'], msg['To'], msg['Subject'] = EMAIL_ZENDER, EMAIL_ONTVANGER or EMAIL_ZENDER, f"🚀 Cloud Bot Koper: {ticker}"
    body = f"Ticker: {ticker}\nPrijs: ${px:.2f}\nSL: ${sl:.2f}\nTP: ${tp:.2f}"
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('://gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ZENDER, EMAIL_WACHTWOORD)
        server.sendmail(EMAIL_ZENDER, msg['To'], msg.as_string())
        server.quit()
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
# 3. LIVE SCANNER EN TRANS-ACTIE LOOP
# =====================================================================
reg = laad_cooldown_register()

# Real-time portfolio controle van openstaande trades
overblijvers = []
for p in st.session_state["portfolio"]:
    try:
        df = yf.Ticker(p["ticker"], session=custom_session).history(period="1d", interval="1m")
        if not df.empty:
            px = float(df["Close"].iloc[-1])
            if px <= p["stop_loss"] or px >= p["take_profit"]:
                reg[p["ticker"].upper()] = datetime.datetime.now() + COOLDOWN_PERIOD
                sla_cooldown_register_op(reg)
                continue
        overblijvers.append(p)
    except Exception: overblijvers.append(p)
st.session_state["portfolio"] = overblijvers

# SCANNEN VAN DE MARKT (5M INTERVALLEN)
for ticker in laad_universe():
    try:
        if not mag_nieuwe_positie_openen(ticker, st.session_state["portfolio"], reg): continue
        df = yf.Ticker(ticker, session=custom_session).history(period="1d", interval="5m")
        if len(df) < 35: continue
        
        df['RSI'] = bereken_rsi(df['Close'])
        macd, sig = bereken_macd(df['Close'])
        
        # Agressievere RSI grens (< 45) + MACD Crossover Check
        if df['RSI'].iloc[-1] < 45 and macd.iloc[-2] <= sig.iloc[-2] and macd.iloc[-1] > sig.iloc[-1]:
            px, sl, tp = bereken_atr_limieten(df)
            st.session_state["portfolio"].append({"ticker": ticker, "entry_price": px, "stop_loss": sl, "take_profit": tp, "shares": 14})
            stur_trade_email(ticker, px, sl, tp)
    except Exception: pass

# =====================================================================
# 4. VISUEEL DASHBOARD & WINSTMETER
# =====================================================================
st.title("📈 Live RSI + MACD Trading Dashboard")
# Bereken de Belgische tijd (Cloud tijd + 2 uur zomertijd)
belgische_tijd = datetime.datetime.now() + datetime.timedelta(hours=2)
st.write(f"Laatste scan succesvol afgerond om: {belgische_tijd.strftime('%H:%M:%S')}")


st.header("📊 Real-time Winstmeter (PnL)")
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Aantal Actieve Posities", value=f"{len(st.session_state['portfolio'])} trades")
with col2:
    st.metric(label="Totale Gerealiseerde PnL", value="$0.00", delta="Winst")

st.markdown("---")
st.subheader("💼 Actieve Portfolio")

if len(st.session_state["portfolio"]) > 0:
    st.write(pd.DataFrame(st.session_state["portfolio"]))
else:
    st.info("Wacht op actieve trades van de 5m Scalper... De pagina ververst live.")

# Automatische pagina-refresh elke 30 seconden om de bot scherp te houden
time.sleep(30)
st.rerun()
