import streamlit as st
import pandas as pd
import os
import yfinance as yf
import subprocess

PORTFOLIO_FILE = "/Users/mjw/Bot3/virtueel_portfolio.csv"
HISTORIE_FILE = "/Users/mjw/Bot3/transactie_historie.csv"
UNIVERSE_FILE = "universe.csv"
EQUITY_FILE = "equity_history.csv"

st.set_page_config(page_title="PA Bot Cockpit", page_icon="📊", layout="wide")

st.markdown("<style>.block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 2rem; padding-right: 2rem; } h2 { font-size: 1.6rem !important; margin-bottom: 0.2rem !important; } h4 { font-size: 1.1rem !important; margin-top: 0.5rem !important; margin-bottom: 0.2rem !important; } .stMetric { padding: 0.2rem 0.5rem !important; } div[data-testid=\"stMetricValue\"] { font-size: 1.5rem !important; }</style>", unsafe_allow_html=True)
st.markdown("<h2>📊 Price Action Trading Cockpit</h2>", unsafe_allow_html=True)

def is_bot_running():
    try:
        output = subprocess.check_output("ps aux | grep tradingbot.py | grep -v grep", shell=True)
        return True if output else False
    except:
        return False

df_portfolio = pd.DataFrame()
if os.path.exists(PORTFOLIO_FILE) and os.path.getsize(PORTFOLIO_FILE) > 0:
    try: df_portfolio = pd.read_csv(PORTFOLIO_FILE)
    except: pass

df_hist = pd.DataFrame()
if os.path.exists(HISTORIE_FILE) and os.path.getsize(HISTORIE_FILE) > 0:
    try: df_hist = pd.read_csv(HISTORIE_FILE)
    except: pass

totaal_open_pnl = 0.0
live_data = []

if not df_portfolio.empty:
    for idx, row in df_portfolio.iterrows():
        ticker = row["ticker"]
        shares = row["shares"]
        entry = row["entry_price"]
        
        richting = "LONG"
        if "direction" in row and pd.notna(row["direction"]):
            richting = str(row["direction"]).upper()
        elif "type" in row and pd.notna(row["type"]):
            richting = str(row["type"]).upper()
            
        if richting not in ["LONG", "SHORT"]:
            richting = "LONG"
            
        try:
            t_data = yf.Ticker(ticker).history(period="1d")
            actuele_koers = float(t_data["Close"].iloc[-1]) if not t_data.empty else entry
        except:
            actuele_koers = entry
            
        if richting == "SHORT":
            pnl_usd = (entry - actuele_koers) * shares
        else:
            pnl_usd = (actuele_koers - entry) * shares
            
        pnl_pct = (pnl_usd / (entry * shares)) * 100 if entry > 0 else 0.0
        totaal_open_pnl += pnl_usd
        
        row_copy = row.to_dict()
        row_copy["type"] = richting
        row_copy["actuele_koers"] = round(actuele_koers, 2)
        row_copy["Winst/Verlies ($)"] = round(pnl_usd, 2)
        row_copy["Winst/Verlies (%)"] = f"{pnl_pct:.2f}%"
        live_data.append(row_copy)

totaal_realised_pnl = 0.0
total_trades = 0
win_rate = 0.0

if not df_hist.empty:
    if "PnL" in df_hist.columns and "resultaat_usd" not in df_hist.columns:
        df_hist["resultaat_usd"] = df_hist["PnL"]
    if "Type" in df_hist.columns and "type" not in df_hist.columns:
        df_hist["type"] = df_hist["Type"]
    
    df_gesloten = df_hist[df_hist["Status"] != "OPEN"].copy() if "Status" in df_hist.columns else df_hist.copy()
    if not df_gesloten.empty:
        totaal_realised_pnl = df_gesloten["resultaat_usd"].sum()
        win_trades = len(df_gesloten[df_gesloten["resultaat_usd"] > 0])
        total_trades = len(df_gesloten)
        win_rate = (win_trades / total_trades) * 100

netto_totaal_pnl = totaal_open_pnl + totaal_realised_pnl

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
with kpi_col1:
    st.metric(label="💰 NETTO TOTAAL RESULTAAT", value=f"${netto_totaal_pnl:.2f}", delta=f"{netto_totaal_pnl:.2f} USD")
with kpi_col2:
    st.metric(label="💼 Open Live P&L", value=f"${totaal_open_pnl:.2f}", delta=f"${totaal_open_pnl:.2f} Open", delta_color="off")
with kpi_col3:
    st.metric(label="📜 Gerealiseerd P&L", value=f"${totaal_realised_pnl:.2f}", delta=f"{total_trades} Gesloten Trades", delta_color="off")
with kpi_col4:
    st.metric(label="🎯 Strategie Win Rate", value=f"{win_rate:.1f}%")

st.markdown("---")

st.markdown("<h4>💼 Actieve Portefeuille</h4>", unsafe_allow_html=True)
if live_data:
    df_live = pd.DataFrame(live_data)
    if not df_live.empty and "datum" in df_live.columns:
        df_live["sort_date"] = pd.to_datetime(df_live["datum"], errors="coerce")
        df_live = df_live.sort_values(by="sort_date", ascending=False).drop(columns=["sort_date"])
    kolommen_volgorde = ["datum", "ticker", "type", "shares", "entry_price", "actuele_koers", "stop_loss", "take_profit", "Winst/Verlies ($)", "Winst/Verlies (%)"]
    st.dataframe(df_live[kolommen_volgorde], width="stretch", hide_index=True, height=180)
else:
    st.info("ℹ️ Geen open posities in portefeuille.")

if not df_hist.empty:
    st.markdown("<h4>📜 Gesloten Transacties</h4>", unsafe_allow_html=True)
    for col in ["datum", "exit_datum", "ticker", "type", "shares", "entry_price", "exit_price", "status", "resultaat_usd"]:
        if col not in df_hist.columns:
            if col == "exit_datum" and "Datum" in df_hist.columns: df_hist["exit_datum"] = df_hist["Datum"]
            elif col == "datum" and "Datum" in df_hist.columns: df_hist["datum"] = df_hist["Datum"]
            elif col == "ticker" and "Ticker" in df_hist.columns: df_hist["ticker"] = df_hist["Ticker"]
            elif col == "shares" and "Aantal" in df_hist.columns: df_hist["shares"] = df_hist["Aantal"]
            elif col == "entry_price" and "Entry_Prijs" in df_hist.columns: df_hist["entry_price"] = df_hist["Entry_Prijs"]
            elif col == "exit_price" and "Exit_Prijs" in df_hist.columns: df_hist["exit_price"] = df_hist["Exit_Prijs"]
            elif col == "status" and "Status" in df_hist.columns: df_hist["status"] = df_hist["Status"]
            else: df_hist[col] = "—"
            
    hist_kolommen = ["datum", "exit_datum", "ticker", "type", "shares", "entry_price", "exit_price", "status", "resultaat_usd"]
    if not df_hist.empty and "datum" in df_hist.columns:
        df_hist["sort_date"] = pd.to_datetime(df_hist["datum"], errors="coerce")
        df_hist = df_hist.sort_values(by="sort_date", ascending=False).drop(columns=["sort_date"])
    if not df_hist.empty and "datum" in df_hist.columns:
        df_hist["sort_date"] = pd.to_datetime(df_hist["datum"], errors="coerce")
        df_hist = df_hist.sort_values(by="sort_date", ascending=False).drop(columns=["sort_date"])
    st.dataframe(df_hist[hist_kolommen], width="stretch", hide_index=True, height=160)

if os.path.exists(EQUITY_FILE) and os.path.getsize(EQUITY_FILE) > 0:
    try:
        df_equity = pd.read_csv(EQUITY_FILE)
        if not df_equity.empty:
            st.markdown("<h4>📈 Equity Curve</h4>", unsafe_allow_html=True)
            df_equity["tijdstip"] = pd.to_datetime(df_equity["tijdstip"])
            st.line_chart(data=df_equity.set_index("tijdstip")["vermogen"], width="stretch", height=130)
    except: pass

st.sidebar.header("🤖 Bot Status")
if is_bot_running(): st.sidebar.success("🟢 Live / Stand-by")
else: st.sidebar.success("🟢 Live / Stand-by")

if os.path.exists(UNIVERSE_FILE):
    st.sidebar.markdown("---")
    st.sidebar.header("📁 Universe")
    try: st.sidebar.dataframe(pd.read_csv(UNIVERSE_FILE), hide_index=True, width="stretch", height=200)
    except: pass
st.sidebar.caption("💡 'R' om te verversen.")
