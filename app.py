import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import re
import tempfile
import json
import contextlib
import yfinance as yf
from src.pdf_parser import parse_erste_pdf
from src.stockwatch_scraper import StockwatchScraper, YFIN_TICKERS

# Set page config for mobile friendliness
st.set_page_config(
    page_title="GPW Smart Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PORTFOLIO_NAMES = {
    "erste": "📈 Erste — Wartościowa",
    "ing":   "🏦 ING — Wartościowa",
    "ikze":  "🔒 IKE/IKZE — Wzrostowa",
}

SCORE_WEIGHTS = {
    "erste": {"cz": 0.30, "cwk": 0.20, "ev": 0.20, "dy": 0.10, "trend": 0.20},
    "ing":   {"cz": 0.30, "cwk": 0.20, "ev": 0.20, "dy": 0.10, "trend": 0.20},
    "ikze":  {"cz": 0.15, "cwk": 0.10, "ev": 0.30, "dy": 0.00, "trend": 0.45},
}

ETF_TICKERS = {"ETFBSPXPL", "ETFBW20TR"}


def get_paths(portfolio: str) -> dict:
    base = os.path.join(BASE_DIR, "data", portfolio)
    os.makedirs(base, exist_ok=True)
    return {
        "holdings":     os.path.join(base, "current_holdings.csv"),
        "history":      os.path.join(base, "portfolio_history.csv"),
        "entry":        os.path.join(base, "entry_prices.json"),
        "deposits":     os.path.join(base, "deposit_history.json"),
        "settings":     os.path.join(base, "portfolio_settings.json"),
        "alerts":       os.path.join(base, "stockwatch_alerts.json"),
        "watchlist":    os.path.join(BASE_DIR, "config", f"{portfolio}_watchlist.json"),
        "transactions": os.path.join(base, "transactions.json"),
    }


def load_settings(settings_path: str) -> dict:
    defaults = {"total_deposits": 0.0, "phpsessid": "", "strategy": "value"}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                data = json.load(f)
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            pass
    with open(settings_path, "w") as f:
        json.dump(defaults, f, indent=2)
    return defaults.copy()


def _comp_scores(c_z, c_wk, ev_ebitda, dy):
    """Component scores (0–100) for each fundamental indicator."""
    if c_z is None:       s_cz = 50.0
    elif c_z < 0:         s_cz = 0.0
    elif c_z < 5:         s_cz = 50.0
    elif c_z <= 12:       s_cz = 100.0
    elif c_z <= 20:       s_cz = 70.0
    elif c_z <= 35:       s_cz = 40.0
    else:                 s_cz = 10.0

    if c_wk is None:      s_cwk = 50.0
    elif c_wk < 0:        s_cwk = 0.0
    elif c_wk <= 1.0:     s_cwk = 100.0
    elif c_wk <= 2.5:     s_cwk = 80.0
    elif c_wk <= 4.0:     s_cwk = 50.0
    else:                 s_cwk = 20.0

    if ev_ebitda is None: s_ev = 50.0
    elif ev_ebitda < 0:   s_ev = 0.0
    elif ev_ebitda <= 6:  s_ev = 100.0
    elif ev_ebitda <= 11: s_ev = 75.0
    elif ev_ebitda <= 16: s_ev = 40.0
    else:                 s_ev = 15.0

    if not dy or dy == 0.0: s_dy = 0.0
    elif dy < 2.0:          s_dy = 30.0
    elif dy < 5.0:          s_dy = 70.0
    elif dy <= 10.0:        s_dy = 100.0
    else:                   s_dy = 80.0

    return s_cz, s_cwk, s_ev, s_dy


def calculate_portfolio_score(indicators: dict, trend_score: float, portfolio: str) -> float:
    w = SCORE_WEIGHTS.get(portfolio, SCORE_WEIGHTS["erste"])
    s_cz, s_cwk, s_ev, s_dy = _comp_scores(
        indicators.get("c_z"), indicators.get("c_wk"),
        indicators.get("ev_ebitda"), indicators.get("dy", 0.0) or 0.0,
    )
    score = (w["cz"] * s_cz + w["cwk"] * s_cwk +
             w["ev"] * s_ev + w["dy"] * s_dy +
             w["trend"] * float(trend_score or 70))
    return round(score, 1)


# Determine active portfolio from session_state (default: erste)
_active_portfolio = st.session_state.get("active_portfolio", "erste")
_paths = get_paths(_active_portfolio)

# Backward-compatible path constants — reassigned per active portfolio
HOLDINGS_PATH        = _paths["holdings"]
HISTORY_PATH         = _paths["history"]
SETTINGS_PATH        = _paths["settings"]
ENTRY_PRICES_PATH    = _paths["entry"]
DEPOSIT_HISTORY_PATH = _paths["deposits"]
WATCHLIST_PATH       = _paths["watchlist"]
TRANSACTIONS_PATH = _paths["transactions"]

os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

SECTORS_MAPPING = {
    # Finanse
    "KRUK":      "Finanse i Windykacja",
    "XTB":       "Finanse i Windykacja",
    "PKOBP":     "Finanse i Windykacja",
    "GPW":       "Finanse i Windykacja",
    "GETIN":     "Finanse i Windykacja",
    "PEKAO":     "Finanse i Windykacja",
    "INGBSK":    "Finanse i Windykacja",
    "BNPPPL":    "Finanse i Windykacja",
    "ERSTE":     "Finanse i Windykacja",
    "PZU":       "Finanse i Ubezpieczenia",
    # Odzież i handel
    "LPP":       "Odzież i Handel",
    "MODIVO":    "Odzież i Handel",
    "ALLEGRO":   "E-commerce i Technologia",
    "ZABKA":     "Handel i Logistyka",
    "ABPL":      "IT i Dystrybucja",
    "INTERCARS": "Handel i Logistyka",
    # Turystyka
    "RAINBOW":   "Rozrywka i Turystyka",
    "KOLEJKOWO": "Rozrywka i Turystyka",
    # Elektrotechnika i energia
    "GRODNO":    "Elektrotechnika i OZE",
    "ELEKTROTI": "Elektrotechnika i OZE",
    "ONDE":      "Energia i OZE",
    "PKNORLEN":  "Energia i Paliwa",
    "KOGENERA":  "Energia i Paliwa",
    "KGHM":      "Surowce i Wydobycie",
    "COGNOR":    "Surowce i Wydobycie",
    # Biotechnologia
    "RYVU":      "Biotechnologia i Medycyna",
    "SYNEKTIK":  "Biotechnologia i Medycyna",
    "SYN2BIO":   "Biotechnologia i Medycyna",
    "MEDINICE":  "Biotechnologia i Medycyna",
    "BIOCELTIX": "Biotechnologia i Medycyna",
    "DIAG":      "Ochrona Zdrowia",
    "NEUCA":     "Ochrona Zdrowia",
    # Budownictwo
    "DOMDEV":    "Budownictwo i Deweloperzy",
    "DEKPOL":    "Budownictwo i Deweloperzy",
    "RANKPROGR": "Budownictwo i Deweloperzy",
    # Przemysł
    "NEWAG":     "Przemysł i Transport",
    "PKPCARGO":  "Przemysł i Transport",
    "TORPOL":    "Przemysł i Transport",
    "LUBAWA":    "Przemysł i Obrona",
    "ZREMB":     "Przemysł i Maszyny",
    "STAPORKOW": "Przemysł i Maszyny",
    "KETY":      "Przemysł i Maszyny",
    "PATENTUS":  "Przemysł i Maszyny",
    # Spożywczy
    "SEKO":      "Przemysł Spożywczy",
    # Technologia i IT
    "CREOTECH":  "Technologia i Kosmonautyka",
    "SCANWAY":   "Technologia i Kosmonautyka",
    "DATAWALK":  "IT i Technologia",
    "CYBERFLKS": "IT i Technologia",
    # Usługi
    "BENEFIT":   "Usługi i HR",
    "MOBRUK":    "Ekologia i Odpady",
    "KLEPSYDRA": "Usługi",
    # ETF
    "ETFBW20TR": "Fundusze ETF",
    "ETFBSPXPL": "Fundusze ETF",
}


def parse_erste_csv(file_obj):
    """
    Parses the Erste BM instrument CSV export (semicolon-delimited, Polish decimal comma).
    Returns (holdings_list, entry_prices_dict, report_date_str, stocks_value).
    Uses 'Prawa własności' as authoritative quantity (total owned, not just available to sell).
    """
    import io
    raw = file_obj.read()
    for enc in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2"):
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            content = None
    if content is None:
        raise ValueError("Nie można odczytać pliku CSV — nieznane kodowanie.")

    df = pd.read_csv(io.StringIO(content), sep=";", dtype=str)
    df.columns = [c.strip() for c in df.columns]

    def _num(val):
        if pd.isna(val) or str(val).strip() in ("", "-", "nan"):
            return None
        return float(str(val).strip().replace("\xa0", "").replace(" ", "").replace(",", ".").replace("%", ""))

    holdings = []
    entry_prices = {}

    for _, row in df.iterrows():
        ticker = str(row.get("Walor", "")).strip()
        if not ticker or ticker == "nan":
            continue

        qty_raw = _num(row.get("Prawa własności"))
        qty = int(qty_raw) if qty_raw is not None else 0

        price = _num(row.get("Kurs bieżący")) or 0.0
        wycena = _num(row.get("Wycena"))
        if wycena is None or wycena == 0:
            wycena = round(qty * price, 2)

        avg_price = _num(row.get("Średni kurs nabycia"))
        isin = str(row.get("ISIN", "")).strip()

        if qty > 0 and price > 0:
            holdings.append({
                "ticker": ticker,
                "isin": isin,
                "quantity": qty,
                "price": price,
                "valuation": wycena,
            })
            if avg_price and avg_price > 0:
                entry_prices[ticker] = avg_price

    stocks_value = sum(h["valuation"] for h in holdings)
    return holdings, entry_prices, stocks_value


def parse_ing_transactions_csv(file_obj):
    """
    Parses ING historiaTransakcji_*.csv (semicolon-delimited, Polish locale, no header).
    Columns: Data;NrZamówienia;Ticker;Typ;Ilość;Cena;Wartość;Prowizja;ŁącznaWartość
    Returns list of transaction dicts ready for merge_ing_transactions().
    """
    import io as _io
    from datetime import datetime as _dt

    raw = file_obj.read()
    for enc in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2"):
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            content = None
    if content is None:
        raise ValueError("Nie można odczytać pliku CSV — nieznane kodowanie.")

    def _num(val):
        s = str(val).strip().replace("\xa0", "").replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
        if not s or s in ("-", "nan"):
            return 0.0
        return float(s)

    transactions = []
    for line in content.strip().splitlines():
        parts = line.split(";")
        if len(parts) < 9:
            continue
        dt_raw, order_id, ticker, typ = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        qty_raw, price_raw, value_raw, fee_raw = parts[4], parts[5], parts[6], parts[7]

        if not ticker or not dt_raw:
            continue
        try:
            dt_obj = _dt.strptime(dt_raw, "%d-%m-%Y %H:%M:%S")
        except ValueError:
            continue

        datetime_iso = dt_obj.strftime("%Y-%m-%dT%H:%M:%S")
        date_iso = dt_obj.strftime("%Y-%m-%d")

        try:
            qty = int(round(_num(qty_raw)))
            price = _num(price_raw)
            value = _num(value_raw)
            fee = _num(fee_raw)
        except (ValueError, TypeError):
            continue

        if qty <= 0 or not ticker:
            continue

        tx_key = f"{datetime_iso}|{order_id}|{ticker}|{typ}|{qty}"
        transactions.append({
            "key":      tx_key,
            "datetime": datetime_iso,
            "date":     date_iso,
            "order_id": order_id,
            "ticker":   ticker,
            "type":     typ,
            "quantity": qty,
            "price":    price,
            "value":    value,
            "fee":      fee,
        })
    return transactions


def merge_ing_transactions(existing: list, new_txs: list) -> tuple:
    """Merge new transactions into existing list, deduplicating by key. Returns (merged, added_count)."""
    existing_keys = {tx["key"] for tx in existing}
    added = [tx for tx in new_txs if tx["key"] not in existing_keys]
    return existing + added, len(added)


def compute_ing_holdings(transactions: list) -> tuple:
    """
    Aggregate ING transaction history into current holdings.
    Returns (holdings_list, entry_prices_dict).
    holdings_list items: {ticker, quantity, price (avg buy), valuation}
    entry_prices_dict: {ticker: avg_buy_price}
    """
    from collections import defaultdict

    pos = defaultdict(lambda: {"qty": 0, "buy_cost": 0.0, "buy_qty": 0})

    for tx in sorted(transactions, key=lambda t: t["datetime"]):
        ticker = tx["ticker"]
        qty = tx["quantity"]
        price = tx["price"]

        if tx["type"] == "Kupno":
            pos[ticker]["qty"] += qty
            pos[ticker]["buy_cost"] += qty * price
            pos[ticker]["buy_qty"] += qty
        elif "Sprzeda" in tx["type"]:
            sell_qty = min(qty, pos[ticker]["qty"])
            if pos[ticker]["buy_qty"] > 0 and sell_qty > 0:
                ratio = sell_qty / pos[ticker]["buy_qty"]
                pos[ticker]["buy_cost"] = max(0.0, pos[ticker]["buy_cost"] - ratio * pos[ticker]["buy_cost"])
                pos[ticker]["buy_qty"] = max(0, pos[ticker]["buy_qty"] - sell_qty)
            pos[ticker]["qty"] = max(0, pos[ticker]["qty"] - sell_qty)

    holdings = []
    entry_prices = {}
    for ticker, p in pos.items():
        qty = p["qty"]
        if qty <= 0:
            continue
        avg_price = round(p["buy_cost"] / p["buy_qty"], 4) if p["buy_qty"] > 0 else 0.0
        holdings.append({
            "ticker":   ticker,
            "quantity": qty,
            "price":    avg_price,
            "valuation": round(qty * avg_price, 2),
        })
        if avg_price > 0:
            entry_prices[ticker] = avg_price

    return holdings, entry_prices


def parse_bos_orders_pdf(pdf_path: str, account_label: str = "") -> list:
    """
    Parses DM BOŚ 'Historia zleceń' PDF (IKE or IKZE account).
    Each transaction occupies 3 text lines:
      Line 1: DD.MM.YYYY  TICKER  VALUE  DD.MM.YYYY
      Line 2: ORDER_NR  K/S  QTY_PLACED  QTY_REAL  LIMIT  wykonane
      Line 3: HH:MM:SS  MARKET  COMMISSION  VALIDITY
    Returns list of transaction dicts compatible with merge_ing_transactions / compute_ing_holdings.
    """
    import pdfplumber
    from datetime import datetime as _dt

    LINE1 = re.compile(
        r'^(\d{2}\.\d{2}\.\d{4})\s+(\S+)\s+(.*?)\s+(\d{2}\.\d{2}\.\d{4})\s*$'
    )
    LINE2 = re.compile(
        r'^(\d{7,12})\s+([KS])\s+(\d+)\s+(\d+)\s+(\S+)\s+wykonane\s*$'
    )

    def _try_line1(line):
        m = LINE1.match(line)
        if not m:
            return None
        date_str, ticker, value_raw, _ = m.groups()
        try:
            value = float(value_raw.replace('\xa0', '').replace(' ', '').replace(',', '.'))
            dt_obj = _dt.strptime(date_str, "%d.%m.%Y")
            return {"date": dt_obj.strftime("%Y-%m-%d"), "ticker": ticker, "value": value}
        except ValueError:
            return None

    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_lines.extend(text.splitlines())

    transactions = []
    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()
        if not line:
            i += 1
            continue

        p1 = _try_line1(line)
        if p1 is None:
            i += 1
            continue

        # Find next non-empty line for LINE2
        j = i + 1
        while j < len(all_lines) and not all_lines[j].strip():
            j += 1
        if j >= len(all_lines):
            break

        m2 = LINE2.match(all_lines[j].strip())
        if not m2:
            i += 1
            continue

        order_nr, ks, _, qty_real, _ = m2.groups()
        try:
            qty = int(qty_real)
        except ValueError:
            i += 1
            continue

        # Find next non-empty line for LINE3 (time + commission)
        k = j + 1
        while k < len(all_lines) and not all_lines[k].strip():
            k += 1
        if k >= len(all_lines):
            break

        parts3 = all_lines[k].strip().split()
        time_match = re.match(r'^\d{2}:\d{2}:\d{2}$', parts3[0]) if parts3 else None
        if not time_match:
            i += 1
            continue

        time_str = parts3[0]
        try:
            commission = float(parts3[-2].replace(',', '.')) if len(parts3) >= 3 else 0.0
        except (ValueError, IndexError):
            commission = 0.0

        eff_price = round(p1["value"] / qty, 4) if qty > 0 else 0.0
        datetime_iso = f"{p1['date']}T{time_str}"
        # Order number is unique per order (not per execution), so key = order_nr + account
        tx_key = f"{order_nr}|{account_label}"

        transactions.append({
            "key":      tx_key,
            "datetime": datetime_iso,
            "date":     p1["date"],
            "order_id": order_nr,
            "ticker":   p1["ticker"],
            "type":     "Kupno" if ks == "K" else "Sprzedaż",
            "quantity": qty,
            "price":    eff_price,
            "value":    p1["value"],
            "fee":      commission,
            "account":  account_label,
        })
        i = k + 1

    return transactions


def load_entry_prices(path=None):
    p = path or ENTRY_PRICES_PATH
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                data = json.load(f)
            return {k: float(v) for k, v in data.items()
                    if not k.startswith("_") and v is not None and float(v) > 0}
        except Exception:
            return {}
    return {}


def load_entry_sources(path=None):
    p = path or ENTRY_PRICES_PATH
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                return json.load(f).get("_src", {})
        except Exception:
            return {}
    return {}


def save_entry_prices(prices_dict, path=None, source=None):
    p = path or ENTRY_PRICES_PATH
    existing = {}
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.update(prices_dict)
    if source:
        _src = existing.get("_src", {})
        for ticker in prices_dict:
            _src[ticker] = source
        existing["_src"] = _src
    with open(p, "w") as f:
        json.dump(existing, f, indent=2)

settings = load_settings(SETTINGS_PATH)

# UXR / CXR Design System — Poppins + Navy + Neon — Mobile First
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* ── Global font ── */
    html, body, [class*="css"], .stMarkdown, .stText, button, input, label, select, textarea {
        font-family: 'Poppins', sans-serif !important;
    }

    /* ── App background ── */
    .stApp { background-color: #f6f6f6; }
    .main .block-container {
        background-color: #f6f6f6;
        padding: 1rem 1.5rem 2rem 1.5rem !important;
        /* fluid: grows with the screen, never wider than 1400px */
        max-width: 1400px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        width: 100% !important;
    }

    /* ── Page title ── */
    h1 { font-family: 'Poppins', sans-serif !important; font-weight: 700 !important;
         color: #131f33 !important; letter-spacing: -0.5px; font-size: 24px !important; }
    h2, h3 { font-family: 'Poppins', sans-serif !important; font-weight: 600 !important;
              color: #1f2b40 !important; }

    /* ── Sidebar — dark navy ── */
    [data-testid="stSidebar"] { background-color: #111926 !important; }
    [data-testid="stSidebar"] * { color: rgba(255,255,255,0.85) !important;
                                   font-family: 'Poppins', sans-serif !important; }
    [data-testid="stSidebar"] svg { fill: rgba(255,255,255,0.65) !important; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ecfa64 !important; font-size: 14px !important; letter-spacing: 0.5px;
    }
    [data-testid="stSidebar"] label { color: rgba(255,255,255,0.6) !important; font-size: 12px !important; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.1) !important; }
    [data-testid="stSidebar"] input {
        background: #1f2b40 !important; color: #fff !important;
        border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 6px !important;
    }
    /* Selectbox — dark background + visible chevron */
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #1f2b40 !important;
        border: 1px solid rgba(255,255,255,0.18) !important;
        border-radius: 6px !important;
    }
    [data-testid="stSidebar"] div[data-baseweb="select"] svg {
        fill: rgba(255,255,255,0.65) !important;
    }
    /* Number input +/- step buttons */
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button {
        background: rgba(255,255,255,0.07) !important;
        border-color: rgba(255,255,255,0.12) !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button:hover {
        background: rgba(255,255,255,0.14) !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button svg {
        fill: rgba(255,255,255,0.75) !important;
    }

    /* ── Tabs — scrollable on mobile ── */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #131f33; border-radius: 10px; padding: 5px; gap: 2px;
        overflow-x: auto; -webkit-overflow-scrolling: touch;
        scrollbar-width: none; flex-wrap: nowrap;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
    .stTabs [data-baseweb="tab"] {
        color: rgba(255,255,255,0.55); font-family: 'Poppins', sans-serif !important;
        font-size: 12px; font-weight: 500; border-radius: 7px;
        padding: 7px 14px; white-space: nowrap; flex-shrink: 0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ecfa64 !important; color: #131f33 !important;
        font-weight: 700 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background-color: #ecfa64 !important; color: #131f33 !important;
        font-family: 'Poppins', sans-serif !important; font-weight: 600 !important;
        border: none !important; border-radius: 8px !important;
        padding: 0.5rem 1rem !important; font-size: 13px !important;
    }
    .stButton > button:hover { background-color: #cde200 !important; }
    /* full-width only when button is inside a block-level container that needs it */
    [data-testid="stVerticalBlock"] > [data-testid="stButton"] > button,
    [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stButton"] > button {
        width: 100% !important;
    }

    /* ── Section divider ── */
    .section-divider {
        border: none; border-top: 1px solid #e8ecf0;
        margin: 20px 0; clear: both;
    }

    /* ── Portfolio context chip ── */
    .portfolio-chip {
        display: inline-flex; align-items: center; gap: 5px;
        border-radius: 20px; padding: 3px 12px;
        font-size: 11px; font-weight: 700;
        font-family: 'Poppins', sans-serif;
        margin-bottom: 10px; margin-top: -4px;
    }

    /* ── Expander header ── */
    [data-testid="stExpander"] summary {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 600 !important; font-size: 13px !important;
        color: #1f2b40 !important;
    }

    /* ── st.info / st.warning style override ── */
    [data-testid="stAlert"] {
        border-radius: 8px !important; font-family: 'Poppins', sans-serif !important;
        font-size: 13px !important;
    }

    /* ── Metric cards grid (mobile-first: 1 col, grows up) ── */
    .metrics-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-bottom: 12px;
    }
    .metric-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        border-left: 4px solid #ecfa64;
        min-height: 90px;
    }
    .metric-card.wide { grid-column: 1 / -1; }
    .metric-title {
        font-family: 'Poppins', sans-serif;
        font-size: 10px;
        color: #808080;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-family: 'Poppins', sans-serif;
        font-size: 18px;
        color: #1a1a1a;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-delta { font-family: 'Poppins', sans-serif; font-size: 11px; font-weight: 500; margin-top: 4px; }
    .delta-plus  { color: #28A745; }
    .delta-minus { color: #DC3545; }

    /* ── Subheader accent ── */
    .uxr-subheader {
        display: flex; align-items: center; gap: 10px; margin: 14px 0 6px 0;
    }
    .uxr-subheader-bar {
        width: 4px; min-height: 24px; background: #ecfa64;
        border-radius: 9999px; flex-shrink: 0;
    }
    .uxr-subheader-text {
        font-family: 'Poppins', sans-serif; font-size: 14px;
        font-weight: 600; color: #1f2b40; letter-spacing: 0.2px;
    }

    /* ── Note / warning cards ── */
    .note-card {
        display: flex; border-radius: 6px; overflow: hidden;
        border: 1.5px solid #e0e0e0; margin-bottom: 8px; background: #fff;
    }
    .note-bar { width: 5px; flex-shrink: 0; }
    .note-bar-warn  { background: #FF9F43; }
    .note-bar-crit  { background: #FF5C5C; }
    .note-bar-info  { background: #5B8DEF; }
    .note-body { padding: 10px 14px; font-family: 'Poppins', sans-serif;
                 font-size: 13px; color: #333; line-height: 1.6; }

    /* ════════════════════════════════════════
       BREAKPOINTS  (mobile-first, grows up)
       ════════════════════════════════════════

       xs  < 480px   — telefon pionowy
       sm  480–767px — telefon poziomy / małe tablety
       md  768–1023px — tablet
       lg  1024–1399px — laptop / desktop
       xl  ≥ 1400px   — wide monitor
    */

    /* xs — telefon pionowy */
    @media (max-width: 479px) {
        .main .block-container { padding: 0.4rem 0.4rem 1rem 0.4rem !important; }
        h1 { font-size: 18px !important; }
        h2 { font-size: 15px !important; }

        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 4px !important; }
        [data-testid="column"] { min-width: 100% !important; flex: 1 1 100% !important; }

        .stTabs [data-baseweb="tab"] { font-size: 10px !important; padding: 5px 8px !important; }

        .metrics-grid { grid-template-columns: 1fr; gap: 8px; }
        .metric-card.wide { grid-column: 1; }
        .metric-value { font-size: 15px !important; }
        .metric-title { font-size: 9px !important; }
        .note-body { font-size: 11px !important; }
    }

    /* sm — telefon poziomy / małe tablety */
    @media (min-width: 480px) and (max-width: 767px) {
        .main .block-container { padding: 0.6rem 0.8rem 1.5rem 0.8rem !important; }
        h1 { font-size: 20px !important; }

        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 6px !important; }
        [data-testid="column"] { min-width: 100% !important; flex: 1 1 100% !important; }

        .stTabs [data-baseweb="tab"] { font-size: 11px !important; padding: 6px 10px !important; }

        .metrics-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
        .metric-card.wide { grid-column: 1 / -1; }
        .metric-value { font-size: 16px !important; }
    }

    /* md — tablet */
    @media (min-width: 768px) and (max-width: 1023px) {
        .main .block-container { padding: 0.8rem 1.2rem 2rem 1.2rem !important; }

        .metrics-grid { grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .metric-card.wide { grid-column: 1 / -1; }
        .metric-value { font-size: 17px !important; }
    }

    /* lg — laptop / desktop */
    @media (min-width: 1024px) and (max-width: 1399px) {
        .metrics-grid { grid-template-columns: repeat(5, 1fr); gap: 12px; }
        .metric-card.wide { grid-column: auto; }
        .metric-value { font-size: 19px !important; }
    }

    /* xl — wide monitor */
    @media (min-width: 1400px) {
        .main .block-container { padding: 1.2rem 3rem 2rem 3rem !important; }
        .metrics-grid { grid-template-columns: repeat(5, 1fr); gap: 14px; }
        .metric-card.wide { grid-column: auto; }
        .metric-card { padding: 18px 20px; min-height: 100px; }
        .metric-value { font-size: 22px !important; }
        .metric-title { font-size: 11px !important; }
        h1 { font-size: 28px !important; }
        .stTabs [data-baseweb="tab"] { font-size: 13px !important; padding: 8px 18px !important; }
    }

    /* ── st.info / st.warning overrides ── */
    [data-testid="stAlert"] { border-radius: 8px !important; font-family: 'Poppins', sans-serif !important; }

    /* ── Scrollable table container (inside iframes) ── */
    .tbl-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📈 GPW Smart Assistant")

_CHIP_COLORS = {
    "erste": ("#5B8DEF", "#e8f0fe"),
    "ing":   ("#5B8DEF", "#e8f0fe"),
    "ikze":  ("#34d399", "#ecfdf5"),
}
_CHIP_LABELS = {
    "erste": "📈 Erste",
    "ing":   "🏦 ING",
    "ikze":  "🔒 IKE/IKZE",
}

def _section_divider():
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

def _portfolio_badge():
    c, bg = _CHIP_COLORS[selected_portfolio]
    label = _CHIP_LABELS[selected_portfolio]
    st.markdown(
        f'<div class="portfolio-chip" style="background:{bg};color:{c};border:1.5px solid {c};">{label}</div>',
        unsafe_allow_html=True,
    )

# ==========================================
# SIDEBAR - PORTFOLIO SELECTOR + CONFIG
# ==========================================
st.sidebar.header("⚙️ Portfele")

selected_portfolio = st.sidebar.selectbox(
    "Aktywny portfel",
    list(PORTFOLIO_NAMES.keys()),
    format_func=lambda k: PORTFOLIO_NAMES[k],
    key="active_portfolio",
)

# If portfolio changed, re-run immediately so path constants update
if selected_portfolio != _active_portfolio:
    st.rerun()

ALERTS_PATH = _paths["alerts"]

st.sidebar.markdown("---")
st.sidebar.markdown("**Suma wpłat zewnętrznych (PLN)**")
st.sidebar.markdown("<div style='font-size:11px;color:rgba(255,255,255,0.75);'>Zysk = Wartość Portfela − Suma Wpłat</div>", unsafe_allow_html=True)

new_total_deposits = st.sidebar.number_input(
    "Wpłaty łącznie (PLN)",
    value=float(settings["total_deposits"]),
    step=500.0,
    format="%.2f",
    label_visibility="collapsed",
)

if new_total_deposits != settings["total_deposits"]:
    settings["total_deposits"] = new_total_deposits
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    if os.path.exists(HISTORY_PATH):
        df_hist = pd.read_csv(HISTORY_PATH)
        if not df_hist.empty:
            df_hist.iloc[-1, df_hist.columns.get_loc("Wpłaty Skumulowane (PLN)")] = new_total_deposits
            latest_val = df_hist.iloc[-1]["Wartość Całkowita (PLN)"]
            df_hist.iloc[-1, df_hist.columns.get_loc("Zysk (PLN)")] = round(latest_val - new_total_deposits, 2)
            df_hist.to_csv(HISTORY_PATH, index=False)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Autoryzacja Stockwatch Premium")
st.sidebar.markdown("""
<div style="font-size:11px;color:rgba(255,255,255,0.78);line-height:1.6;margin-bottom:8px;">
Stockwatch.pl używa <b style="color:#ecfa64;">ASP.NET_SessionId</b> — nie PHPSESSID.<br><br>
<b>Jak znaleźć:</b><br>
① Zaloguj się na stockwatch.pl<br>
② DevTools (F12) → <b>Application</b><br>
③ Cookies → <b>https://www.stockwatch.pl</b><br>
④ Skopiuj wartość <b>ASP.NET_SessionId</b>
</div>
""", unsafe_allow_html=True)
new_phpsessid = st.sidebar.text_input(
    "ASP.NET_SessionId (cookie sesji)",
    value=settings.get("phpsessid", ""),
    type="password",
)

if new_phpsessid != settings.get("phpsessid", ""):
    settings["phpsessid"] = new_phpsessid
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    st.rerun()

# Portfolio strategy badge in sidebar
_strat_badge = {"erste": "#5B8DEF", "ing": "#5B8DEF", "ikze": "#34d399"}
_strat_label = {"erste": "Wartościowa", "ing": "Wartościowa", "ikze": "Wzrostowa (IKE/IKZE)"}
st.sidebar.markdown(f"""
<div style="margin-top:12px;padding:8px 12px;background:rgba(255,255,255,0.06);border-radius:8px;border-left:3px solid {_strat_badge[selected_portfolio]};">
  <div style="font-size:11px;color:rgba(255,255,255,0.72);">Strategia aktywna</div>
  <div style="font-size:13px;font-weight:700;color:{_strat_badge[selected_portfolio]};">{_strat_label[selected_portfolio]}</div>
</div>
""", unsafe_allow_html=True)

# TAB NAVIGATION
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "☀️ Rekomendacje 8:00",
    "🎯 Strategia",
    "📊 Wyniki i Portfel",
    "🔔 Alerty Stockwatch",
    "💰 Inwestuj",
])

# ==========================================
# TAB 1 & 2: REKOMENDACJE I STRATEGIA
# ==========================================
with tab1:
    _tab1_title = "☀️ Rekomendacje Sesyjne" if selected_portfolio != "ikze" else "🔍 Analiza Wzrostowa (Kwartalny Przegląd)"
    st.header(_tab1_title)
    _portfolio_badge()
    st.markdown("System pobierania i wieloczynnikowej analizy wskaźników giełdowych przed otwarciem sesji o 9:00.")

    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, "r") as f:
                watchlist = json.load(f)
        except Exception:
            watchlist = ["KRUK", "LPP", "GRODNO", "RYVU", "SYNEKTIK", "MODIVO", "NEWAG", "GPW", "SEKO", "DOMDEV", "XTB"]
    else:
        watchlist = ["KRUK", "LPP", "GRODNO", "RYVU", "SYNEKTIK", "MODIVO", "NEWAG", "GPW", "SEKO", "DOMDEV", "XTB"]

    if "recommendations_data" not in st.session_state:
        st.session_state["recommendations_data"] = None

    source_status = "🔑 Stockwatch Premium (L1)" if settings.get("phpsessid") else "📊 Biznesradar.pl (L2)"
    st.markdown(f"""
    <div class="note-card">
      <div class="note-bar note-bar-info"></div>
      <div class="note-body" style="font-size:12px;">
        <b>Spółki ({len(watchlist)}):</b> {' · '.join(watchlist)}<br>
        <b>Źródło danych:</b> {source_status} &nbsp;|&nbsp; <b>Model:</b> {"C/Z 15% · C/WK 10% · EV 30% · DY 0% · Trend 45% (Wzrostowy)" if selected_portfolio == "ikze" else "C/Z 30% · C/WK 20% · EV/EBITDA 20% · DY 10% · Trend 20% (Wartościowy)"}
      </div>
    </div>
    """, unsafe_allow_html=True)

    _wl_file = f"config/{selected_portfolio}_watchlist.json"
    with st.expander(f"📋 Obserwowane spółki ({len(watchlist)}) — jak dodać nową?"):
        st.markdown("**Aktualna watchlista:**")
        _wl_cols = st.columns(4)
        for _i, _t in enumerate(watchlist):
            _wl_cols[_i % 4].markdown(f"• `{_t}`")
        st.markdown("---")
        st.markdown("**Jak dodać nową spółkę do obserwacji?**")
        st.markdown(f"""
**Krok 1 — dodaj ticker do watchlisty** (`{_wl_file}`):
```json
["TICKER_NOWEJ_SPOLKI", ...istniejące...]
```

**Krok 2 — zarejestruj spółkę w scraperze** (`src/stockwatch_scraper.py`):

W słowniku `STOCKWATCH_SLUGS` dodaj:
```python
"TICKER": "slug-ze-stockwatch",   # np. "DINO": "dino-polska"
```
Slug to końcówka URL ze strony spółki na stockwatch.pl, np. `stockwatch.pl/gpw/dino-polska,notowania.aspx` → slug = `dino-polska`.

W słowniku `YFIN_TICKERS` dodaj:
```python
"TICKER": "TICKER.WA",   # np. "DINO": "DNP.WA"
```
Symbol Yahoo Finance znajdziesz na finance.yahoo.com — zwykle to skrót GPW + `.WA`.

W słowniku `STATIC_FALLBACKS` dodaj minimalne dane awaryjne:
```python
"TICKER": {{"price": 0, "c_z": None, "c_wk": None, "ev_ebitda": None, "dy": None}},
```

**Krok 3 — zrestartuj aplikację** (Streamlit odświeży watchlistę automatycznie po restarcie).
""")

    # Warn about analysis time before button
    _est_min = max(1, len(watchlist) // 10)
    st.markdown(f"""
    <div class="note-card">
      <div class="note-bar note-bar-warn"></div>
      <div class="note-body" style="font-size:12px;">
        ⏱️ Analiza <b>{len(watchlist)} spółek</b> pobiera dane sekwencyjnie — szacowany czas: <b>{_est_min}–{_est_min*2} min</b>.
        Uruchom przed sesją (np. o 8:00). Wyniki zapisują się w pamięci do czasu odświeżenia strony.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Warn if portfolio holds tickers not in watchlist
    if os.path.exists(HOLDINGS_PATH):
        try:
            _df_hold_check = pd.read_csv(HOLDINGS_PATH)
            _missing_from_wl = [t for t in _df_hold_check["Spółka"].tolist() if t not in watchlist]
            if _missing_from_wl:
                st.markdown(f"""
                <div class="note-card">
                  <div class="note-bar note-bar-warn"></div>
                  <div class="note-body" style="font-size:12px;">
                    ⚠️ Spółki w portfelu, których <b>nie ma na watchliście</b> (brak analizy w Tab 1):
                    <b>{', '.join(_missing_from_wl)}</b>.<br>
                    Dodaj je do <code>config/{selected_portfolio}_watchlist.json</code> i scraperów, aby objąć analizą.
                  </div>
                </div>
                """, unsafe_allow_html=True)
        except Exception:
            pass

    if st.button("🔄 Uruchom Analizę", use_container_width=True, type="primary"):
        with st.spinner("Pobieranie wskaźników..."):
            scraper = StockwatchScraper(phpsessid=settings.get("phpsessid", ""))
            recom_data = []
            for ticker in watchlist:
                indicators = scraper.get_indicators(ticker)
                trend_score = scraper.get_technical_trend(ticker)
                score = calculate_portfolio_score(indicators, trend_score, selected_portfolio)
                recom = scraper.get_recommendation(score)
                # IKE/IKZE: rename KUPUJ → AKUMULUJ (długoterminowa semantyka)
                if selected_portfolio == "ikze" and recom["action"] == "KUPUJ":
                    recom = dict(recom, action="AKUMULUJ")
                recom_data.append({
                    "ticker": ticker,
                    "c_z": indicators.get("c_z"),
                    "c_wk": indicators.get("c_wk"),
                    "ev_ebitda": indicators.get("ev_ebitda"),
                    "dy": indicators.get("dy"),
                    "price": indicators.get("price"),
                    "trend_score": trend_score,
                    "score": score,
                    "action": recom["action"],
                    "color": recom["color"],
                    "text_color": recom["text_color"],
                    "source": indicators.get("source", "Nieznane")
                })
            st.session_state["recommendations_data"] = recom_data
            st.success(f"Analiza zakończona — {len(recom_data)} spółek.")
            st.rerun()

    st.markdown("---")

    if st.session_state["recommendations_data"] is not None:
        recom_list = st.session_state["recommendations_data"]

        rows_html = ""
        for row in recom_list:
            if row['c_z'] is None:
                cz_val = "N/A"
            elif row['c_z'] < 0:
                cz_val = "Strata"
            else:
                cz_val = f"{row['c_z']:.2f}"
            cwk_val = f"{row['c_wk']:.2f}" if row['c_wk'] is not None else "N/A"
            ev_val = f"{row['ev_ebitda']:.2f}" if row['ev_ebitda'] is not None else "N/A"
            dy_val = f"{row['dy']:.2f}%" if row['dy'] is not None and row['dy'] > 0 else "0.00%"
            price_val = f"{row['price']:,.2f} zł" if row['price'] is not None else "N/A"
            is_l3 = "Lokalna" in row['source']
            trend_label = "&#x1F4C8; Wzrostowy" if row['trend_score'] == 100 else "&#x1F4C9; Spadkowy"
            trend_color = "#27ae60" if row['trend_score'] == 100 else "#e74c3c"
            src_color = ("#7c3aed" if "Premium" in row['source']
                         else "#16a34a" if "Biznesradar" in row['source']
                         else "#2563eb" if "Yahoo" in row['source']
                         else "#6b7280")
            if is_l3:
                score_cell = '<span style="color:#9ca3af;font-size:12px;font-style:italic;">—</span>'
                recom_cell = '<span style="border:1.5px solid #d1d5db;color:#9ca3af;padding:5px 14px;border-radius:20px;font-size:11px;font-weight:600;">Brak danych</span>'
                trend_label = '<span style="color:#9ca3af;font-size:12px;font-style:italic;">—</span>'
                trend_color = "#9ca3af"
            else:
                score_bg = "#dcfce7" if row['score'] >= 70 else ("#fee2e2" if row['score'] <= 30 else "#fef9c3")
                score_color = "#166534" if row['score'] >= 70 else ("#991b1b" if row['score'] <= 30 else "#854d0e")
                score_cell = f'<span style="background:{score_bg};color:{score_color};padding:4px 10px;border-radius:6px;font-weight:700;font-size:13px;">{row["score"]:.1f}</span>'
                recom_cell = f'<span style="background:{row["color"]};color:{row["text_color"]};padding:5px 14px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">{row["action"]}</span>'

            rows_html += f"""
            <tr>
                <td class="td-company">{row['ticker']}</td>
                <td class="td-num">{price_val}</td>
                <td class="td-center">{cz_val}</td>
                <td class="td-center">{cwk_val}</td>
                <td class="td-center">{ev_val}</td>
                <td class="td-center td-green">{dy_val}</td>
                <td style="padding:12px 16px;font-size:12px;font-weight:600;color:{trend_color};">{trend_label}</td>
                <td class="td-center">{score_cell}</td>
                <td class="td-center">{recom_cell}</td>
                <td class="td-center"><span style="border:1.5px solid {src_color};color:{src_color};padding:2px 7px;border-radius:4px;font-size:9px;font-weight:700;">{row['source']}</span></td>
            </tr>"""

        table_html = f"""<!DOCTYPE html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            *{{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif;}}
            html,body{{background:#f6f6f6;}}
            .wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;padding:4px;border-radius:10px;}}
            table{{min-width:700px;width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);}}
            thead tr{{background:#131f33;border-bottom:3px solid #ecfa64;}}
            th{{padding:10px 12px;font-size:10px;font-weight:600;color:rgba(255,255,255,0.7);text-align:left;text-transform:uppercase;letter-spacing:0.8px;white-space:nowrap;}}
            th.th-center{{text-align:center;}}
            tbody tr{{border-bottom:1px solid #f0f0f0;transition:background .15s;}}
            tbody tr:hover{{background:#f8f8f8;}}
            td{{padding:10px 12px;font-size:12px;color:#333;white-space:nowrap;}}
            .td-company{{font-weight:700;color:#131f33;font-size:13px;}}
            .td-num{{font-weight:600;color:#1a1a1a;}}
            .td-center{{text-align:center;}}
            .td-green{{color:#16a34a;font-weight:600;}}
        </style></head><body>
        <div class="wrap"><table>
            <thead><tr>
                <th>Spółka</th><th>Kurs</th>
                <th class="th-center">C/Z</th><th class="th-center">C/WK</th>
                <th class="th-center">EV/EBITDA</th><th class="th-center">DY%</th>
                <th>Trend</th><th class="th-center">Score</th>
                <th class="th-center">Rekomen.</th><th class="th-center">Źródło</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table></div></body></html>"""

        table_height = len(recom_list) * 50 + 60
        components.html(table_html, height=table_height, scrolling=False)
    else:
        st.info("Brak załadowanych rekomendacji. Kliknij przycisk powyżej, aby wygenerować rekomendacje sesyjne o 8:00.")

with tab2:
    st.header("🎯 Realizacja Strategii Portfela")
    _portfolio_badge()
    st.markdown("Nadzór nad limitami alokacji kapitału oraz kontrola ryzyka (Stop-Loss / Take-Profit).")

    if os.path.exists(HOLDINGS_PATH):
        df_holdings = pd.read_csv(HOLDINGS_PATH)
    else:
        df_holdings = pd.DataFrame()

    if df_holdings.empty:
        st.markdown("""
        <div class="note-card">
          <div class="note-bar note-bar-warn"></div>
          <div class="note-body">
            Brak danych portfela. Przejdź do zakładki <b>📊 Wyniki i Portfel</b> i wgraj plik CSV lub PDF.
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        # Initialize live prices from the holdings CSV (purchase price as default)
        if "live_prices" not in st.session_state or not st.session_state["live_prices"]:
            st.session_state["live_prices"] = {row["Spółka"]: row["Kurs (PLN)"] for _, row in df_holdings.iterrows()}
        if "live_sources" not in st.session_state:
            st.session_state["live_sources"] = {row["Spółka"]: "Cena zakupu (PDF)" for _, row in df_holdings.iterrows()}

        st.markdown("""
        <div class="note-card">
          <div class="note-bar note-bar-info"></div>
          <div class="note-body" style="font-size:12px;">
            Limit spółki: <b>15%</b> &nbsp;|&nbsp; Limit sektora: <b>30%</b> &nbsp;|&nbsp;
            Stop-Loss: <b>−10%</b> &nbsp;|&nbsp; Take-Profit: <b>+25%</b>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Entry price editor
        entry_prices_saved = load_entry_prices()
        with st.expander("✏️ Edytuj Ceny Wejścia (rzeczywiste ceny zakupu)"):
            st.markdown("Wpisz rzeczywiste ceny zakupu dla każdej pozycji. Zostaną użyte w obliczeniach Stop-Loss / Take-Profit zamiast cen z PDF.")
            ep_cols = st.columns(3)
            ep_inputs = {}
            for i, (_, row) in enumerate(df_holdings.iterrows()):
                ticker = row["Spółka"]
                default_val = entry_prices_saved.get(ticker, row["Kurs (PLN)"])
                with ep_cols[i % 3]:
                    ep_inputs[ticker] = st.number_input(
                        f"{ticker} ({int(row['Ilość'])} szt.)",
                        min_value=0.01,
                        value=float(default_val),
                        step=0.01,
                        format="%.2f",
                        key=f"ep_{ticker}"
                    )
            if st.button("💾 Zapisz Ceny Wejścia", use_container_width=True):
                save_entry_prices(ep_inputs, source="manual")
                st.success("Ceny wejścia zapisane!")
                st.rerun()

        if st.button("🔄 Odśwież Kursy", use_container_width=True):
            with st.spinner("Pobieranie aktualnych notowań (Stockwatch → Biznesradar → Yahoo)..."):
                scraper_strat = StockwatchScraper(phpsessid=settings.get("phpsessid", ""))
                live_prices = {}
                live_sources = {}
                for ticker in df_holdings["Spółka"].unique():
                    indicators = scraper_strat.get_indicators(ticker)
                    price = indicators.get("price")
                    source = indicators.get("source", "")
                    if price and "Lokalna" not in source:
                        live_prices[ticker] = float(price)
                        live_sources[ticker] = source
                    else:
                        live_prices[ticker] = float(
                            df_holdings.loc[df_holdings["Spółka"] == ticker, "Kurs (PLN)"].values[0]
                        )
                        live_sources[ticker] = "Cena zakupu (PDF)"
                st.session_state["live_prices"] = live_prices
                st.session_state["live_sources"] = live_sources
                st.success("Zaktualizowano kursy!")
                st.rerun()

        # Recalculate valuations based on live prices
        df_strat = df_holdings.copy()
        df_strat["Sektor"] = df_strat["Spółka"].map(lambda x: SECTORS_MAPPING.get(x, "Inne i Fundusze"))
        df_strat["Kurs Bieżący (PLN)"] = df_strat["Spółka"].map(lambda x: st.session_state["live_prices"].get(x, df_strat.loc[df_strat["Spółka"] == x, "Kurs (PLN)"].values[0]))
        df_strat["Wycena Bieżąca (PLN)"] = df_strat["Ilość"] * df_strat["Kurs Bieżący (PLN)"]
        
        total_live_stocks_val = df_strat["Wycena Bieżąca (PLN)"].sum()
        if total_live_stocks_val == 0:
            total_live_stocks_val = 1.0
        df_strat["Udział Bieżący (%)"] = round((df_strat["Wycena Bieżąca (PLN)"] / total_live_stocks_val) * 100, 2)
        
        # Allocation warning checks — different logic per portfolio
        allocation_warnings = []
        df_sect = df_strat.groupby("Sektor")["Wycena Bieżąca (PLN)"].sum().reset_index()
        df_sect["Udział (%)"] = round((df_sect["Wycena Bieżąca (PLN)"] / total_live_stocks_val) * 100, 2)

        if selected_portfolio == "ikze":
            # IKE/IKZE: rebalancing alarm (ETF target 60%, single position limit 15%)
            etf_val = df_strat.loc[df_strat["Spółka"].isin(ETF_TICKERS), "Wycena Bieżąca (PLN)"].sum()
            etf_pct = etf_val / total_live_stocks_val * 100
            if etf_pct < 55:
                allocation_warnings.append(f"🔄 **Rebalansowanie wymagane — ETF:** Udział ETF wynosi **{etf_pct:.1f}%** (cel 60%, próg min 55%). Doważyć ETFBSPXPL lub ETFBW20TR.")
            elif etf_pct > 65:
                allocation_warnings.append(f"🔄 **Rebalansowanie wymagane — ETF:** Udział ETF wynosi **{etf_pct:.1f}%** (cel 60%, próg max 65%). Rozważyć zwiększenie growth stocks.")
            for _, r in df_strat.iterrows():
                if r["Udział Bieżący (%)"] > 15.0 and r["Spółka"] not in ETF_TICKERS:
                    excess_pln = r["Wycena Bieżąca (PLN)"] - (total_live_stocks_val * 0.15)
                    allocation_warnings.append(f"⚠️ **Koncentracja IKE/IKZE ({r['Spółka']}):** Udział wynosi **{r['Udział Bieżący (%)']:.2f}%** (limit 15%). Nadwyżka: **{excess_pln:,.2f} zł**.")
        else:
            # Erste/ING: standard limits 15%/30%
            for _, r in df_strat.iterrows():
                if r["Udział Bieżący (%)"] > 15.0:
                    excess_pln = r["Wycena Bieżąca (PLN)"] - (total_live_stocks_val * 0.15)
                    allocation_warnings.append(f"⚠️ **Przekroczenie limitu alokacji spółki ({r['Spółka']}):** Udział wynosi **{r['Udział Bieżący (%)']:.2f}%** (limit 15%). Nadwyżka: **{excess_pln:,.2f} zł**. Sugerowana redukcja.")
            for _, r in df_sect.iterrows():
                if r["Udział (%)"] > 30.0:
                    excess_pln = r["Wycena Bieżąca (PLN)"] - (total_live_stocks_val * 0.30)
                    allocation_warnings.append(f"🚨 **Krytyczne przekroczenie sektora ({r['Sektor']}):** Udział wynosi **{r['Udział (%)']:.2f}%** (limit 30%). Nadwyżka: **{excess_pln:,.2f} zł**. Sugerowane rebalansowanie.")

        if allocation_warnings:
            st.markdown('<div class="uxr-subheader"><div class="uxr-subheader-bar"></div><div class="uxr-subheader-text">⚠️ Ostrzeżenia Alokacyjne (Quality Gate)</div></div>', unsafe_allow_html=True)
            for warn in allocation_warnings:
                bar_cls = "note-bar-crit" if "Krytyczne" in warn else "note-bar-warn"
                st.markdown(f'<div class="note-card"><div class="note-bar {bar_cls}"></div><div class="note-body">{warn}</div></div>', unsafe_allow_html=True)
            st.markdown("---")

        # Visual charts — side by side on wide screens, stacked on mobile (via CSS)
        col_ch1, col_ch2 = st.columns([1, 1])
        UXR_COLORS = ["#131f33", "#1f2b40", "#ecfa64", "#cde200", "#5B8DEF", "#FF9F43", "#FF5C5C", "#34d399", "#a78bfa", "#f87171"]

        with col_ch1:
            fig_stock_alloc = px.bar(
                df_strat.sort_values(by="Udział Bieżący (%)", ascending=True),
                x="Udział Bieżący (%)", y="Spółka", orientation="h",
                title="Udział Spółek w Portfelu (%)",
                color="Udział Bieżący (%)",
                color_continuous_scale=[[0, "#1f2b40"], [0.5, "#5B8DEF"], [1, "#ecfa64"]]
            )
            fig_stock_alloc.add_vline(x=15.0, line_dash="dash", line_color="#FF5C5C",
                                       annotation_text="Limit 15%", annotation_font_color="#FF5C5C")
            fig_stock_alloc.update_layout(
                margin=dict(l=10, r=10, t=40, b=10), showlegend=False, coloraxis_showscale=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Poppins, sans-serif", color="#1a1a1a"),
                title_font=dict(family="Poppins, sans-serif", size=14, color="#131f33"),
                yaxis=dict(gridcolor="#f0f0f0"), xaxis=dict(gridcolor="#f0f0f0")
            )
            st.plotly_chart(fig_stock_alloc, use_container_width=True)

        with col_ch2:
            fig_sect_alloc = px.pie(
                df_sect, names="Sektor", values="Wycena Bieżąca (PLN)",
                hole=0.45, title="Alokacja Sektorowa (%)",
                color_discrete_sequence=UXR_COLORS
            )
            fig_sect_alloc.update_layout(
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Poppins, sans-serif", color="#1a1a1a"),
                title_font=dict(family="Poppins, sans-serif", size=14, color="#131f33")
            )
            st.plotly_chart(fig_sect_alloc, use_container_width=True)

        # Risk Management (Stop-Loss & Take-Profit)
        st.markdown('<div class="uxr-subheader"><div class="uxr-subheader-bar"></div><div class="uxr-subheader-text">&#128721; Monitor Ryzyka (Stop-Loss &amp; Take-Profit)</div></div>', unsafe_allow_html=True)

        risk_rows_html = ""
        entry_prices_for_risk = load_entry_prices()
        entry_sources_for_risk = load_entry_sources()
        _no_entry_prices = not bool(entry_prices_for_risk)

        if _no_entry_prices:
            st.markdown("""
            <div class="note-card">
              <div class="note-bar note-bar-crit"></div>
              <div class="note-body">
                <b>Brak cen wejścia</b> — kolumna <em>Wynik (%)</em> liczy zmianę od bieżącego kursu
                zamiast od rzeczywistej ceny zakupu. Wgraj CSV z kolumną <b>Średni kurs nabycia</b>
                (Tab 3 → CSV) lub wpisz ręcznie w ekspanderze powyżej.
              </div>
            </div>
            """, unsafe_allow_html=True)

        _src_label = {"csv": "Śr. nabycia", "manual": "Ręczna"}
        for _, r in df_strat.iterrows():
            ticker_name = r["Spółka"]
            pdf_price = r["Kurs (PLN)"]
            entry_val = entry_prices_for_risk.get(ticker_name)
            if entry_val and float(entry_val) > 0:
                purchase = float(entry_val)
                _raw_src = entry_sources_for_risk.get(ticker_name, "manual")
                purchase_source = _src_label.get(_raw_src, "Ręczna")
            else:
                purchase = float(pdf_price)
                purchase_source = "Bieżący"
            current = r["Kurs Bieżący (PLN)"]
            change_pct = ((current - purchase) / purchase) * 100 if purchase > 0 else 0.0
            change_str = f"{change_pct:+.2f}%"
            change_color = "#16a34a" if change_pct >= 0 else "#dc2626"
            src = st.session_state.get("live_sources", {}).get(ticker_name, "")
            src_color = ("#7c3aed" if "Premium" in src
                         else "#16a34a" if "Biznesradar" in src
                         else "#2563eb" if "Yahoo" in src
                         else "#9ca3af")

            _is_dust = r["Udział Bieżący (%)"] < 0.1
            if _is_dust:
                badge = '<span style="background:#9ca3af;color:#fff;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#128309; PYŁ &lt;0.1%</span>'
                row_bg = "#f9fafb"
            elif selected_portfolio == "ikze":
                # IKE/IKZE: no SL/TP, quarterly review badges
                if change_pct >= 50.0:
                    badge = '<span style="background:#7c3aed;color:#fff;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#128200; PRZEJRZYJ +50%</span>'
                    row_bg = "#f5f3ff"
                elif change_pct <= -20.0:
                    badge = '<span style="background:#ea580c;color:#fff;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#128204; DO PRZEGLĄDU</span>'
                    row_bg = "#fff7ed"
                else:
                    badge = '<span style="background:#065f46;color:#ecfa64;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#9651; TRZYMAJ</span>'
                    row_bg = "#ffffff"
            else:
                if change_pct <= -10.0:
                    badge = '<span style="background:#dc2626;color:#fff;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#128721; STOP-LOSS!</span>'
                    row_bg = "#fff5f5"
                elif change_pct >= 25.0:
                    badge = '<span style="background:#16a34a;color:#fff;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#9989; TAKE-PROFIT!</span>'
                    row_bg = "#f0fdf4"
                else:
                    badge = '<span style="background:#131f33;color:#ecfa64;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#9711; OK</span>'
                    row_bg = "#ffffff"

            src_badge = f'<span style="border:1.5px solid {src_color};color:{src_color};padding:1px 6px;border-radius:4px;font-size:9px;font-weight:700;">{src.split("(")[0].strip() or "PDF"}</span>'
            ep_badge_color = ("#16a34a" if purchase_source == "Śr. nabycia"
                              else "#7c3aed" if purchase_source == "Ręczna"
                              else "#9ca3af")
            ep_badge = f'<span style="border:1.5px solid {ep_badge_color};color:{ep_badge_color};padding:1px 6px;border-radius:4px;font-size:9px;font-weight:700;">{purchase_source}</span>'

            risk_rows_html += f"""
            <tr style="background:{row_bg};">
                <td class="td-company">{ticker_name}</td>
                <td class="td-num">{int(r['Ilość']):,}</td>
                <td class="td-num">{purchase:,.2f} zł {ep_badge}</td>
                <td class="td-num td-bold">{current:,.2f} zł</td>
                <td style="padding:10px 12px;font-size:14px;font-weight:700;color:{change_color};">{change_str}</td>
                <td class="td-center">{badge}</td>
                <td class="td-center">{src_badge}</td>
            </tr>"""

        risk_html = f"""<!DOCTYPE html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            *{{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif;}}
            html,body{{background:#f6f6f6;}}
            .wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;padding:4px;border-radius:10px;}}
            table{{min-width:560px;width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);}}
            thead tr{{background:#131f33;border-bottom:3px solid #ecfa64;}}
            th{{padding:10px 12px;font-size:10px;font-weight:600;color:rgba(255,255,255,0.7);text-align:left;text-transform:uppercase;letter-spacing:0.8px;white-space:nowrap;}}
            th.th-center{{text-align:center;}}
            tbody tr{{border-bottom:1px solid #f0f0f0;}}
            td{{padding:10px 12px;font-size:13px;color:#333;white-space:nowrap;}}
            .td-company{{font-weight:700;color:#131f33;}}
            .td-num{{font-weight:500;}}
            .td-bold{{font-weight:700;color:#1a1a1a;}}
            .td-center{{text-align:center;}}
        </style></head><body>
        <div class="wrap"><table>
            <thead><tr>
                <th>Spółka</th><th>Ilość</th>
                <th>Cena Wejścia</th><th>Kurs Bieżący</th>
                <th>Wynik (%)</th><th class="th-center">Status</th><th class="th-center">Źródło</th>
            </tr></thead>
            <tbody>{risk_rows_html}</tbody>
        </table></div></body></html>"""

        risk_height = len(df_strat) * 50 + 60
        components.html(risk_html, height=risk_height, scrolling=False)

# ==========================================
# TAB 3: WYNIKI PORTFELA (CEL 3)
# ==========================================
with tab3:
    _tab3_names = {"erste": "Erste BM", "ing": "ING Bank Polska", "ikze": "IKE/IKZE"}
    st.header(f"📊 Wyniki Portfela — {_tab3_names[selected_portfolio]}")
    _portfolio_badge()
    
    # 1. WGRYWANIE DANYCH PORTFELA
    if selected_portfolio == "ing":
        _exp_label = "📥 Wgraj / Edytuj dane portfela ING"
    elif selected_portfolio == "ikze":
        _exp_label = "📥 Wgraj Historię Zleceń DM BOŚ (IKE + IKZE)"
    else:
        _exp_label = "📥 Wgraj dane portfela"
    with st.expander(_exp_label):
        if selected_portfolio == "ing":
            _tab_labels = ["✏️ Ręczna edycja", "📄 CSV", "📑 PDF"]
            _upload_tabs = st.tabs(_tab_labels)
            upload_tab_manual = _upload_tabs[0]
            upload_tab_csv    = _upload_tabs[1]
            upload_tab_pdf    = _upload_tabs[2]
        elif selected_portfolio == "ikze":
            _tab_labels = ["📑 Historia zleceń DM BOŚ (IKE + IKZE)", "✏️ Ręczna edycja"]
            _upload_tabs = st.tabs(_tab_labels)
            upload_tab_pdf    = _upload_tabs[0]
            upload_tab_manual = _upload_tabs[1]
            upload_tab_csv    = None
        else:
            _tab_labels = ["📄 CSV — Wykaz instrumentów (zalecane)", "📑 PDF — Raport kwartalny", "✏️ Ręczna edycja"]
            _upload_tabs = st.tabs(_tab_labels)
            upload_tab_csv    = _upload_tabs[0]
            upload_tab_pdf    = _upload_tabs[1]
            upload_tab_manual = _upload_tabs[2]

        # ── MANUAL EDITOR (primary for ING, fallback for others) ──────────────
        with upload_tab_manual:
            st.markdown("Edytuj pozycje bezpośrednio w tabeli. Kurs bieżący wpisz ręcznie lub odśwież przez Tab 2.")
            _empty_row = {"Spółka": "", "Ilość": 0, "Kurs (PLN)": 0.0, "Wycena (PLN)": 0.0, "Udział (%)": 0.0}
            if os.path.exists(HOLDINGS_PATH):
                _df_manual = pd.read_csv(HOLDINGS_PATH)
            else:
                _df_manual = pd.DataFrame([_empty_row])
            _edited = st.data_editor(
                _df_manual,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Spółka": st.column_config.TextColumn("Ticker", width="small"),
                    "Ilość": st.column_config.NumberColumn("Ilość", min_value=0, step=1),
                    "Kurs (PLN)": st.column_config.NumberColumn("Kurs (PLN)", min_value=0.0, format="%.2f"),
                    "Wycena (PLN)": st.column_config.NumberColumn("Wycena (PLN)", format="%.2f", disabled=True),
                    "Udział (%)": st.column_config.NumberColumn("Udział (%)", format="%.2f", disabled=True),
                },
                key=f"manual_editor_{selected_portfolio}",
            )
            if st.button("💾 Zapisz zmiany portfela", use_container_width=True, key="save_manual"):
                _edited = _edited.dropna(subset=["Spółka"]).copy()
                _edited = _edited[_edited["Spółka"].str.strip() != ""]
                _edited["Wycena (PLN)"] = (_edited["Ilość"] * _edited["Kurs (PLN)"]).round(2)
                _total_m = _edited["Wycena (PLN)"].sum() or 1.0
                _edited["Udział (%)"] = (_edited["Wycena (PLN)"] / _total_m * 100).round(2)
                _edited.to_csv(HOLDINGS_PATH, index=False)
                st.success(f"Zapisano {len(_edited)} pozycji portfela {PORTFOLIO_NAMES[selected_portfolio]}!")
                st.rerun()

        # ── CSV UPLOADER (nie dotyczy IKZE — nie ma eksportu CSV z DM BOŚ) ──
        _csv_ctx = upload_tab_csv if upload_tab_csv is not None else contextlib.nullcontext()
        with _csv_ctx:
            if selected_portfolio == "ing":
                st.markdown("""
                <div class="note-card">
                  <div class="note-bar note-bar-info"></div>
                  <div class="note-body" style="font-size:12px;">
                    Wgraj plik <b>historiaTransakcji_*.csv</b> z ING Banku (Moje Finanse → Makler → Historia transakcji → Eksport CSV).<br>
                    Format: <em>Data;NrZamówienia;Ticker;Typ;Ilość;Cena;Wartość;Prowizja;ŁącznaWartość</em><br>
                    Transakcje są porównywane po dacie, numerze zamówienia, tickerze i ilości — duplikaty są automatycznie pomijane.<br>
                    <b>Bonus:</b> średnia cena nabycia wyliczana z historii transakcji jest automatycznie wczytana jako cena wejścia w Tab 2.
                  </div>
                </div>
                """, unsafe_allow_html=True)
                # Show existing transaction summary
                if os.path.exists(TRANSACTIONS_PATH):
                    try:
                        with open(TRANSACTIONS_PATH, "r") as _f:
                            _existing_txs = json.load(_f)
                        _tx_dates = sorted({tx["date"] for tx in _existing_txs})
                        st.info(f"Baza transakcji ING: **{len(_existing_txs)}** rekordów, zakres dat: {_tx_dates[0] if _tx_dates else '—'} → {_tx_dates[-1] if _tx_dates else '—'}")
                    except Exception:
                        _existing_txs = []
                else:
                    _existing_txs = []

                uploaded_csv = st.file_uploader("Wybierz plik historiaTransakcji_*.csv", type=["csv"], key="csv_uploader")
                if uploaded_csv is not None:
                    _csv_id = f"{uploaded_csv.name}_{uploaded_csv.size}"
                    if st.session_state.get("_csv_processed_id") == _csv_id:
                        st.success(f"Plik {uploaded_csv.name} już wczytany — dane są aktualne.")
                    else:
                        try:
                            with st.spinner("Przetwarzanie historii transakcji ING..."):
                                new_txs = parse_ing_transactions_csv(uploaded_csv)
                                merged_txs, added_count = merge_ing_transactions(_existing_txs, new_txs)
                                holdings_csv, entry_prices_csv = compute_ing_holdings(merged_txs)

                            if not holdings_csv:
                                st.error("Brak aktywnych pozycji po przetworzeniu transakcji. Sprawdź format pliku.")
                            else:
                                # Save merged transaction history
                                with open(TRANSACTIONS_PATH, "w") as _f:
                                    json.dump(sorted(merged_txs, key=lambda t: t["datetime"]), _f, indent=2, ensure_ascii=False)

                                # Save current holdings
                                stocks_val_csv = sum(h["valuation"] for h in holdings_csv)
                                total_s = stocks_val_csv or 1.0
                                holdings_rows = []
                                for h in sorted(holdings_csv, key=lambda x: -x["valuation"]):
                                    holdings_rows.append({
                                        "Spółka": h["ticker"],
                                        "Ilość": h["quantity"],
                                        "Kurs (PLN)": h["price"],
                                        "Wycena (PLN)": h["valuation"],
                                        "Udział (%)": round(h["valuation"] / total_s * 100, 2),
                                    })
                                pd.DataFrame(holdings_rows).to_csv(HOLDINGS_PATH, index=False)

                                if entry_prices_csv:
                                    save_entry_prices(entry_prices_csv, source="csv")

                                # Update portfolio history with today's date
                                rep_date_csv = pd.Timestamp.today().strftime("%Y-%m-%d")
                                df_hist = pd.read_csv(HISTORY_PATH) if os.path.exists(HISTORY_PATH) else pd.DataFrame(columns=["Data", "Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"])
                                df_hist["Data"] = df_hist["Data"].astype(str)
                                new_hist_row = {
                                    "Data": rep_date_csv,
                                    "Wartość Całkowita (PLN)": stocks_val_csv,
                                    "Wycena Akcji (PLN)": stocks_val_csv,
                                    "Gotówka (PLN)": 0.0,
                                    "Wpłaty Skumulowane (PLN)": settings["total_deposits"],
                                    "Zysk (PLN)": round(stocks_val_csv - settings["total_deposits"], 2),
                                }
                                if rep_date_csv in df_hist["Data"].values:
                                    for col in ["Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"]:
                                        df_hist.loc[df_hist["Data"] == rep_date_csv, col] = new_hist_row[col]
                                else:
                                    df_hist = pd.concat([df_hist, pd.DataFrame([new_hist_row])], ignore_index=True)
                                    df_hist = df_hist.sort_values(by="Data").reset_index(drop=True)
                                df_hist.to_csv(HISTORY_PATH, index=False)

                                ep_info = f" Ceny wejścia: {len(entry_prices_csv)} spółek." if entry_prices_csv else ""
                                dup_info = f" Pominięto {len(new_txs) - added_count} duplikatów." if len(new_txs) - added_count > 0 else ""
                                st.success(f"Dodano {added_count} nowych transakcji ({len(merged_txs)} łącznie). Portfel: {len(holdings_csv)} pozycji, {stocks_val_csv:,.2f} PLN.{ep_info}{dup_info}")
                                st.session_state["_csv_processed_id"] = _csv_id
                                st.session_state.pop("live_prices", None)
                                st.session_state.pop("live_sources", None)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Błąd przetwarzania historii transakcji ING: {e}")
            else:
                st.markdown("""
                <div class="note-card">
                  <div class="note-bar note-bar-info"></div>
                  <div class="note-body" style="font-size:12px;">
                    Wgraj plik <b>Instrumenty_finansowe_raport_*.csv</b> z Erste BM.<br>
                    CSV nie zawiera danych osobowych (PESEL, numer rachunku) — jest bezpieczny dla repozytorium.<br>
                    <b>Bonus:</b> kolumna <em>Średni kurs nabycia</em> zostanie automatycznie wczytana jako ceny wejścia w Tab 2.
                  </div>
                </div>
                """, unsafe_allow_html=True)
                uploaded_csv = st.file_uploader("Wybierz plik CSV", type=["csv"], key="csv_uploader")
                if uploaded_csv is not None:
                    _csv_id = f"{uploaded_csv.name}_{uploaded_csv.size}"
                    if st.session_state.get("_csv_processed_id") == _csv_id:
                        st.success(f"Plik {uploaded_csv.name} już wczytany — dane są aktualne.")
                    else:
                        try:
                            with st.spinner("Przetwarzanie pliku CSV..."):
                                holdings_csv, entry_prices_csv, stocks_val_csv = parse_erste_csv(uploaded_csv)

                            if not holdings_csv:
                                st.error("Nie znaleziono pozycji w pliku CSV. Sprawdź format pliku.")
                            else:
                                fname = uploaded_csv.name
                                date_m = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
                                rep_date_csv = date_m.group(1) if date_m else pd.Timestamp.today().strftime("%Y-%m-%d")

                                total_s = stocks_val_csv if stocks_val_csv else 1.0
                                holdings_rows = []
                                for h in sorted(holdings_csv, key=lambda x: -x["valuation"]):
                                    holdings_rows.append({
                                        "Spółka": h["ticker"],
                                        "Ilość": h["quantity"],
                                        "Kurs (PLN)": h["price"],
                                        "Wycena (PLN)": h["valuation"],
                                        "Udział (%)": round(h["valuation"] / total_s * 100, 2),
                                    })
                                pd.DataFrame(holdings_rows).to_csv(HOLDINGS_PATH, index=False)

                                if entry_prices_csv:
                                    save_entry_prices(entry_prices_csv, source="csv")

                                df_hist = pd.read_csv(HISTORY_PATH) if os.path.exists(HISTORY_PATH) else pd.DataFrame(columns=["Data", "Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"])
                                df_hist["Data"] = df_hist["Data"].astype(str)
                                new_hist_row = {
                                    "Data": rep_date_csv,
                                    "Wartość Całkowita (PLN)": stocks_val_csv,
                                    "Wycena Akcji (PLN)": stocks_val_csv,
                                    "Gotówka (PLN)": 0.0,
                                    "Wpłaty Skumulowane (PLN)": settings["total_deposits"],
                                    "Zysk (PLN)": round(stocks_val_csv - settings["total_deposits"], 2),
                                }
                                if rep_date_csv in df_hist["Data"].values:
                                    for col in ["Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"]:
                                        df_hist.loc[df_hist["Data"] == rep_date_csv, col] = new_hist_row[col]
                                else:
                                    df_hist = pd.concat([df_hist, pd.DataFrame([new_hist_row])], ignore_index=True)
                                    df_hist = df_hist.sort_values(by="Data").reset_index(drop=True)
                                df_hist.to_csv(HISTORY_PATH, index=False)

                                ep_info = f" Wczytano {len(entry_prices_csv)} cen wejścia." if entry_prices_csv else ""
                                st.success(f"Wczytano {rep_date_csv} — {len(holdings_csv)} spółek, {stocks_val_csv:,.2f} PLN.{ep_info}")
                                st.session_state["_csv_processed_id"] = _csv_id
                                st.session_state.pop("live_prices", None)
                                st.session_state.pop("live_sources", None)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Błąd przetwarzania CSV: {e}")

        # ── PDF UPLOADER ───────────────────────────────────────────────────────
        with upload_tab_pdf:
            if selected_portfolio == "ikze":
                # ── DM BOŚ Historia zleceń — dwa pliki: IKE + IKZE ────────────
                st.markdown("""
                <div class="note-card">
                  <div class="note-bar note-bar-info"></div>
                  <div class="note-body" style="font-size:12px;">
                    Wgraj pliki <b>Historia zleceń</b> z DM BOŚ (online.bossa.pl → Historia zleceń → filtr: <em>wykonane</em> → Pobierz PDF).<br>
                    Wgraj oba rachunki (IKE <b>i</b> IKZE) — transakcje zostaną scalone w jeden portfel.<br>
                    Każdy import jest bezpieczny — duplikaty są automatycznie pomijane (deduplikacja po numerze zlecenia).
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Load existing transactions
                if os.path.exists(TRANSACTIONS_PATH):
                    try:
                        with open(TRANSACTIONS_PATH, "r") as _f:
                            _existing_bos_txs = json.load(_f)
                        _bos_dates = sorted({tx["date"] for tx in _existing_bos_txs})
                        _ike_cnt  = sum(1 for t in _existing_bos_txs if t.get("account") == "IKE")
                        _ikze_cnt = sum(1 for t in _existing_bos_txs if t.get("account") == "IKZE")
                        st.info(f"Baza transakcji: **{len(_existing_bos_txs)}** rekordów (IKE: {_ike_cnt}, IKZE: {_ikze_cnt}), zakres: {_bos_dates[0] if _bos_dates else '—'} → {_bos_dates[-1] if _bos_dates else '—'}")
                    except Exception:
                        _existing_bos_txs = []
                else:
                    _existing_bos_txs = []

                col_ike, col_ikze = st.columns(2)
                with col_ike:
                    st.markdown("**Rachunek IKE**")
                    up_ike = st.file_uploader("Historia zleceń IKE", type=["pdf"], key="pdf_ike_uploader")
                with col_ikze:
                    st.markdown("**Rachunek IKZE**")
                    up_ikze = st.file_uploader("Historia zleceń IKZE", type=["pdf"], key="pdf_ikze_uploader")

                def _process_bos_pdf(uploaded, account_label, existing_txs):
                    """Parse one DM BOŚ PDF, merge into existing transactions, save and return merged list."""
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_f:
                        tmp_f.write(uploaded.read())
                        tmp_path = tmp_f.name
                    try:
                        new_txs = parse_bos_orders_pdf(tmp_path, account_label)
                        merged, added = merge_ing_transactions(existing_txs, new_txs)
                        return merged, added, len(new_txs)
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                def _save_bos_holdings(merged_txs):
                    """Recompute holdings from all transactions and persist."""
                    holdings_h, entry_prices_h = compute_ing_holdings(merged_txs)
                    with open(TRANSACTIONS_PATH, "w") as _f:
                        json.dump(sorted(merged_txs, key=lambda t: t["datetime"]), _f, indent=2, ensure_ascii=False)
                    if not holdings_h:
                        return 0, 0.0
                    stocks_val = sum(h["valuation"] for h in holdings_h)
                    total_s = stocks_val or 1.0
                    rows = []
                    for h in sorted(holdings_h, key=lambda x: -x["valuation"]):
                        rows.append({
                            "Spółka": h["ticker"],
                            "Ilość": h["quantity"],
                            "Kurs (PLN)": h["price"],
                            "Wycena (PLN)": h["valuation"],
                            "Udział (%)": round(h["valuation"] / total_s * 100, 2),
                        })
                    pd.DataFrame(rows).to_csv(HOLDINGS_PATH, index=False)
                    if entry_prices_h:
                        save_entry_prices(entry_prices_h, source="csv")
                    rep_date = pd.Timestamp.today().strftime("%Y-%m-%d")
                    df_hist = pd.read_csv(HISTORY_PATH) if os.path.exists(HISTORY_PATH) else pd.DataFrame(columns=["Data", "Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"])
                    df_hist["Data"] = df_hist["Data"].astype(str)
                    new_hist = {"Data": rep_date, "Wartość Całkowita (PLN)": stocks_val, "Wycena Akcji (PLN)": stocks_val, "Gotówka (PLN)": 0.0, "Wpłaty Skumulowane (PLN)": settings["total_deposits"], "Zysk (PLN)": round(stocks_val - settings["total_deposits"], 2)}
                    if rep_date in df_hist["Data"].values:
                        for col in new_hist:
                            if col != "Data":
                                df_hist.loc[df_hist["Data"] == rep_date, col] = new_hist[col]
                    else:
                        df_hist = pd.concat([df_hist, pd.DataFrame([new_hist])], ignore_index=True).sort_values("Data").reset_index(drop=True)
                    df_hist.to_csv(HISTORY_PATH, index=False)
                    return len(holdings_h), stocks_val

                # Process IKE PDF
                if up_ike is not None:
                    _ike_id = f"ike_{up_ike.name}_{up_ike.size}"
                    if st.session_state.get("_bos_ike_processed_id") == _ike_id:
                        st.success(f"IKE: {up_ike.name} już wczytany.")
                    else:
                        try:
                            with st.spinner("Przetwarzanie IKE PDF..."):
                                _cur_txs = _existing_bos_txs[:]
                                merged_txs, added, total_new = _process_bos_pdf(up_ike, "IKE", _cur_txs)
                                pos_count, stocks_val = _save_bos_holdings(merged_txs)
                            dup = total_new - added
                            st.success(f"IKE: dodano {added} nowych zleceń ({dup} duplikatów pominięto). Portfel: {pos_count} pozycji, {stocks_val:,.2f} PLN.")
                            st.session_state["_bos_ike_processed_id"] = _ike_id
                            st.session_state.pop("live_prices", None)
                            st.session_state.pop("live_sources", None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Błąd przetwarzania IKE PDF: {e}")

                # Process IKZE PDF
                if up_ikze is not None:
                    _ikze_id = f"ikze_{up_ikze.name}_{up_ikze.size}"
                    if st.session_state.get("_bos_ikze_processed_id") == _ikze_id:
                        st.success(f"IKZE: {up_ikze.name} już wczytany.")
                    else:
                        try:
                            # Reload transactions in case IKE was just processed
                            _cur_txs2 = []
                            if os.path.exists(TRANSACTIONS_PATH):
                                with open(TRANSACTIONS_PATH) as _f2:
                                    _cur_txs2 = json.load(_f2)
                            with st.spinner("Przetwarzanie IKZE PDF..."):
                                merged_txs2, added2, total_new2 = _process_bos_pdf(up_ikze, "IKZE", _cur_txs2)
                                pos_count2, stocks_val2 = _save_bos_holdings(merged_txs2)
                            dup2 = total_new2 - added2
                            st.success(f"IKZE: dodano {added2} nowych zleceń ({dup2} duplikatów pominięto). Portfel: {pos_count2} pozycji, {stocks_val2:,.2f} PLN.")
                            st.session_state["_bos_ikze_processed_id"] = _ikze_id
                            st.session_state.pop("live_prices", None)
                            st.session_state.pop("live_sources", None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Błąd przetwarzania IKZE PDF: {e}")

            else:
                # ── Erste BM PDF (fallback for erste; ING doesn't use this path) ──
                st.markdown("""
                <div class="note-card">
                  <div class="note-bar note-bar-warn"></div>
                  <div class="note-body" style="font-size:12px;">
                    ⚠️ <b>Ostrzeżenie o prywatności:</b> Raporty PDF z Erste BM mogą zawierać
                    numer rachunku, PESEL i inne dane osobowe. Plik jest przetwarzany tylko lokalnie
                    i nie jest zapisywany — ale przy deploymencie na Streamlit Cloud przechodzi przez
                    ich serwery. <b>Zalecane jest używanie wyciągu CSV zamiast PDF.</b>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                uploaded_file = st.file_uploader("Wybierz plik PDF wyciągu", type=["pdf"], key="pdf_uploader")
                if uploaded_file is not None:
                    _pdf_id = f"{uploaded_file.name}_{uploaded_file.size}"
                    if st.session_state.get("_pdf_processed_id") == _pdf_id:
                        st.success(f"Plik {uploaded_file.name} już wczytany — dane są aktualne.")
                    else:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(uploaded_file.read())
                            tmp_path = tmp_file.name
                        try:
                            with st.spinner("Przetwarzanie raportu PDF..."):
                                parsed_data = parse_erste_pdf(tmp_path)
                            if parsed_data["report_date"] is not None:
                                rep_date = parsed_data["report_date"]
                                df_history = pd.read_csv(HISTORY_PATH) if os.path.exists(HISTORY_PATH) else pd.DataFrame(columns=["Data", "Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"])
                                df_history["Data"] = df_history["Data"].astype(str)
                                val = parsed_data["total_value"] if parsed_data["total_value"] is not None else parsed_data["stocks_value"]
                                new_row = {"Data": rep_date, "Wartość Całkowita (PLN)": val, "Wycena Akcji (PLN)": parsed_data["stocks_value"], "Gotówka (PLN)": parsed_data.get("cash_value", parsed_data.get("cash_val", 0.0)), "Wpłaty Skumulowane (PLN)": settings["total_deposits"], "Zysk (PLN)": round(val - settings["total_deposits"], 2)}
                                if rep_date in df_history["Data"].values:
                                    for col in ["Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"]:
                                        df_history.loc[df_history["Data"] == rep_date, col] = new_row[col]
                                else:
                                    df_history = pd.concat([df_history, pd.DataFrame([new_row])], ignore_index=True)
                                    df_history = df_history.sort_values(by="Data").reset_index(drop=True)
                                df_history.to_csv(HISTORY_PATH, index=False)
                                if parsed_data["holdings"]:
                                    holdings_list = []
                                    total_stocks = parsed_data["stocks_value"] or sum(h["valuation"] for h in parsed_data["holdings"]) or 1.0
                                    for h in parsed_data["holdings"]:
                                        holdings_list.append({"Spółka": h["ticker"], "Ilość": h["quantity"], "Kurs (PLN)": h["price"], "Wycena (PLN)": h["valuation"], "Udział (%)": round((h["valuation"] / total_stocks) * 100, 2)})
                                    pd.DataFrame(holdings_list).sort_values(by="Wycena (PLN)", ascending=False).reset_index(drop=True).to_csv(HOLDINGS_PATH, index=False)
                                st.success(f"Wczytano raport z dnia {rep_date}!")
                                st.session_state["_pdf_processed_id"] = _pdf_id
                                st.session_state.pop("live_prices", None)
                                st.session_state.pop("live_sources", None)
                                st.rerun()
                            else:
                                st.error("Nie udało się sparsować raportu. Upewnij się, że wgrywasz poprawny wyciąg z Erste BM.")
                        except Exception as e:
                            st.error(f"Wystąpił błąd podczas przetwarzania pliku PDF: {str(e)}")
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)

    # 2. KEY METRICS (KPIs)
    # Load history data to calculate KPIs
    if os.path.exists(HISTORY_PATH):
        df_history = pd.read_csv(HISTORY_PATH)
        df_history = df_history.sort_values(by="Data").reset_index(drop=True)
    else:
        df_history = pd.DataFrame()

    if not df_history.empty:
        # Get latest stats
        latest_row = df_history.iloc[-1]
        latest_val = latest_row["Wartość Całkowita (PLN)"]
        latest_stocks = latest_row["Wycena Akcji (PLN)"]
        latest_cash = latest_row["Gotówka (PLN)"]
        latest_date = latest_row["Data"]
        
        # Calculate daily change (Wynik z ostatniego dnia vs dzień poprzedni)
        if len(df_history) >= 2:
            prev_row = df_history.iloc[-2]
            prev_val = prev_row["Wartość Całkowita (PLN)"]
            daily_change_pln = latest_val - prev_val
            daily_change_pct = (daily_change_pln / prev_val) * 100
            daily_delta_str = f"{daily_change_pln:+.2f} zł ({daily_change_pct:+.2f}%) vs poprz. wgranie"
            daily_delta_class = "delta-plus" if daily_change_pln >= 0 else "delta-minus"
        else:
            daily_change_pln = 0.0
            daily_change_pct = 0.0
            daily_delta_str = "Brak wcześniejszych danych"
            daily_delta_class = ""
            
        # Calculate change vs cumulative deposits (Organic Profit)
        latest_deposits = latest_row["Wpłaty Skumulowane (PLN)"] if "Wpłaty Skumulowane (PLN)" in latest_row else settings["total_deposits"]
        organic_profit_pln = latest_val - latest_deposits
        total_change_pct = (organic_profit_pln / latest_deposits) * 100 if latest_deposits > 0 else 0.0
        total_delta_str = f"{organic_profit_pln:+.2f} zł ({total_change_pct:+.2f}%) zysku netto bez wpłat"
        total_delta_class = "delta-plus" if organic_profit_pln >= 0 else "delta-minus"
        
        # KPI grid — CSS auto-wrap: 1 col mobile → 2 col tablet → 5 col desktop
        st.markdown(f"""
        <div class="metrics-grid">
          <div class="metric-card wide">
            <div class="metric-title">Wycena Portfela ({latest_date})</div>
            <div class="metric-value">{latest_val:,.2f} PLN</div>
            <div class="metric-delta {daily_delta_class}">Zmiana: {daily_change_pln:+.2f} PLN vs poprz. wgranie</div>
          </div>
          <div class="metric-card" style="border-left-color:#27ae60;">
            <div class="metric-title">Zmiana od ost. wgrania</div>
            <div class="metric-value">{daily_change_pln:+.2f} PLN</div>
            <div class="metric-delta {daily_delta_class}">{daily_change_pct:+.2f}%</div>
          </div>
          <div class="metric-card" style="border-left-color:#cde200;">
            <div class="metric-title">Zysk Netto (od startu)</div>
            <div class="metric-value">{total_change_pct:+.2f}%</div>
            <div class="metric-delta {total_delta_class}">{organic_profit_pln:+.2f} PLN</div>
          </div>
          <div class="metric-card" style="border-left-color:#5B8DEF;">
            <div class="metric-title">Suma Wpłat</div>
            <div class="metric-value">{latest_deposits:,.2f} PLN</div>
            <div class="metric-delta" style="color:#808080;">Kapitał zewnętrzny</div>
          </div>
          <div class="metric-card" style="border-left-color:#FF9F43;">
            <div class="metric-title">Gotówka (wg CSV)</div>
            <div class="metric-value">{latest_cash:,.2f} PLN</div>
            <div class="metric-delta" style="color:#808080;">Wyciąg CSV nie zawiera salda</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""<div class="note-card"><div class="note-bar note-bar-warn"></div>
        <div class="note-body">Brak danych historycznych. Wgraj CSV lub PDF w sekcji powyżej.</div></div>""",
        unsafe_allow_html=True)

    _section_divider()

    # 3. WYKRES EWOLUCJI PORTFELA + ZNACZNIKI WPŁAT
    if not df_history.empty:
        st.markdown('<div class="uxr-subheader"><div class="uxr-subheader-bar"></div><div class="uxr-subheader-text">📈 Ewolucja Portfela, Zysku i Sumy Wpłat</div></div>', unsafe_allow_html=True)

        # Load deposit history
        deposits = []
        if os.path.exists(DEPOSIT_HISTORY_PATH):
            try:
                with open(DEPOSIT_HISTORY_PATH, "r", encoding="utf-8") as _f:
                    deposits = json.load(_f)
            except Exception:
                deposits = []

        # Convert dates to datetime for proper vline positioning
        df_history["Data_dt"] = pd.to_datetime(df_history["Data"])
        df_plot = df_history.melt(
            id_vars=["Data_dt"],
            value_vars=["Wartość Całkowita (PLN)", "Zysk (PLN)", "Wpłaty Skumulowane (PLN)"],
            var_name="Wskaźnik",
            value_name="Wartość (PLN)"
        )

        fig = px.line(
            df_plot, x="Data_dt", y="Wartość (PLN)", color="Wskaźnik",
            title="Ewolucja Wartości Portfela vs Zysk Organiczny vs Suma Wpłat",
            markers=True,
            color_discrete_map={
                "Wartość Całkowita (PLN)": "#131f33",
                "Zysk (PLN)": "#cde200",
                "Wpłaty Skumulowane (PLN)": "#5B8DEF"
            }
        )

        # Add vertical markers for each deposit within chart date range
        chart_min = df_history["Data_dt"].min()
        chart_max = df_history["Data_dt"].max()
        for dep in deposits:
            dep_dt = pd.to_datetime(dep["date"])
            if chart_min <= dep_dt <= chart_max:
                fig.add_vline(
                    x=dep_dt,
                    line_dash="dot", line_color="#5B8DEF", line_width=1.5,
                    annotation_text=f"+{dep['amount']:,.0f}",
                    annotation_font=dict(size=9, color="#5B8DEF", family="Poppins, sans-serif"),
                    annotation_position="top left",
                    annotation_bgcolor="rgba(255,255,255,0.75)",
                )

        fig.update_layout(
            hovermode="x unified",
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title=None, yaxis_title="Wartość (PLN)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Poppins, sans-serif", color="#1a1a1a"),
            title_font=dict(family="Poppins, sans-serif", size=15, color="#131f33"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(family="Poppins, sans-serif")),
            yaxis=dict(gridcolor="#f0f0f0"),
            xaxis=dict(gridcolor="#f0f0f0", tickformat="%d %b %Y")
        )
        st.plotly_chart(fig, use_container_width=True)

    # 3b. HISTORIA WPŁAT NA RACHUNEK
    st.markdown('<div class="uxr-subheader"><div class="uxr-subheader-bar"></div><div class="uxr-subheader-text">💳 Historia Wpłat (ostatnie 12 miesięcy)</div></div>', unsafe_allow_html=True)

    deposits_for_chart = []
    if os.path.exists(DEPOSIT_HISTORY_PATH):
        try:
            with open(DEPOSIT_HISTORY_PATH, "r", encoding="utf-8") as _f:
                deposits_for_chart = json.load(_f)
        except Exception:
            deposits_for_chart = []

    if deposits_for_chart:
        df_dep = pd.DataFrame(deposits_for_chart)
        df_dep["date"] = pd.to_datetime(df_dep["date"])
        df_dep = df_dep.sort_values("date").reset_index(drop=True)
        df_dep["cumulative"] = df_dep["amount"].cumsum()
        dep_total = df_dep["amount"].sum()
        dep_count = len(df_dep)

        fig_dep = go.Figure()
        fig_dep.add_trace(go.Bar(
            x=df_dep["date"], y=df_dep["amount"],
            name="Wpłata", marker_color="#5B8DEF",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Wpłata: %{y:,.0f} PLN<extra></extra>"
        ))
        fig_dep.add_trace(go.Scatter(
            x=df_dep["date"], y=df_dep["cumulative"],
            name="Narastająco", mode="lines+markers",
            line=dict(color="#ecfa64", width=2),
            marker=dict(size=6, color="#ecfa64"),
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Łącznie: %{y:,.0f} PLN<extra></extra>",
            yaxis="y2"
        ))
        fig_dep.update_layout(
            title=f"Wpłaty na rachunek — {dep_count} transakcji, łącznie {dep_total:,.0f} PLN",
            title_font=dict(family="Poppins, sans-serif", size=14, color="#131f33"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Poppins, sans-serif", color="#1a1a1a"),
            margin=dict(l=10, r=10, t=50, b=10),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(gridcolor="#f0f0f0", tickformat="%d %b %Y"),
            yaxis=dict(title="Kwota (PLN)", gridcolor="#f0f0f0", side="left"),
            yaxis2=dict(title="Narastająco (PLN)", overlaying="y", side="right",
                        showgrid=False, tickformat=",.0f")
        )
        st.plotly_chart(fig_dep, use_container_width=True)

        # Deposit table
        with st.expander("📋 Tabela wpłat"):
            df_dep_disp = df_dep[["date", "amount", "cumulative"]].copy()
            df_dep_disp.columns = ["Data", "Kwota (PLN)", "Narastająco (PLN)"]
            df_dep_disp["Data"] = df_dep_disp["Data"].dt.strftime("%d.%m.%Y")
            df_dep_disp["Kwota (PLN)"] = df_dep_disp["Kwota (PLN)"].map(lambda x: f"{x:,.2f} zł")
            df_dep_disp["Narastająco (PLN)"] = df_dep_disp["Narastająco (PLN)"].map(lambda x: f"{x:,.2f} zł")
            st.dataframe(df_dep_disp.iloc[::-1].reset_index(drop=True),
                         use_container_width=True, hide_index=True)
    else:
        st.info("Brak pliku historii wpłat (data/deposit_history.json).")
        
    # 4. STRUCTURA I SKŁAD PORTFELA
    st.markdown('<div class="uxr-subheader"><div class="uxr-subheader-bar"></div><div class="uxr-subheader-text">🥧 Skład i Struktura Portfela</div></div>', unsafe_allow_html=True)
    
    if os.path.exists(HOLDINGS_PATH):
        df_holdings = pd.read_csv(HOLDINGS_PATH)
    else:
        df_holdings = pd.DataFrame()
        
    if not df_holdings.empty:
        col_pie, col_table = st.columns([1, 1])
        
        with col_pie:
            # Pie chart for portfolio structure
            df_pie = df_holdings.copy()
            df_pie.loc[df_pie['Udział (%)'] < 2.5, 'Spółka'] = 'Inne'
            
            fig_pie = px.pie(
                df_pie, names="Spółka", values="Wycena (PLN)", hole=0.45,
                title="Struktura Portfela",
                color_discrete_sequence=["#131f33","#1f2b40","#ecfa64","#cde200",
                                         "#5B8DEF","#FF9F43","#FF5C5C","#34d399","#a78bfa","#f87171"]
            )
            fig_pie.update_layout(
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Poppins, sans-serif"),
                title_font=dict(family="Poppins, sans-serif", size=14, color="#131f33")
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_table:
            # Beautiful data table
            st.markdown("##### Wykaz Aktywów")
            
            # Format numbers for elegant Polish-localized look
            df_disp = df_holdings.copy()
            df_disp["Ilość"] = df_disp["Ilość"].map(lambda x: f"{x:,}")
            df_disp["Kurs (PLN)"] = df_disp["Kurs (PLN)"].map(lambda x: f"{x:,.2f} zł")
            df_disp["Wycena (PLN)"] = df_disp["Wycena (PLN)"].map(lambda x: f"{x:,.2f} zł")
            df_disp["Udział (%)"] = df_disp["Udział (%)"].map(lambda x: f"{x:.2f}%")
            
            st.dataframe(df_disp, use_container_width=True, hide_index=True)
    else:
        st.info("Wgraj raport PDF, który zawiera wykaz posiadanych instrumentów finansowych, aby wyświetlić ich strukturę.")

# ==========================================
# TAB 4: ALERTY STOCKWATCH PREMIUM
# ==========================================
with tab4:
    st.header("🔔 Alerty Stockwatch — Nowe Analizy")
    _portfolio_badge()
    st.markdown("Monitoruje pojawienie się nowych analiz technicznych i fundamentalnych na Stockwatch Premium dla spółek z Twojego portfela i watchlisty.")

    has_cookie = bool(settings.get("phpsessid", "").strip())

    if not has_cookie:
        st.markdown("""
        <div class="note-card">
          <div class="note-bar note-bar-warn"></div>
          <div class="note-body">
            <b>Wymagane: ciasteczko sesji ASP.NET_SessionId</b><br>
            Bez niego Stockwatch Premium nie udostępnia analiz. Wpisz wartość w sidebarze (lewy panel).<br><br>
            <b>Jak znaleźć:</b> F12 → Application → Cookies → https://www.stockwatch.pl → skopiuj <b>ASP.NET_SessionId</b>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="note-card"><div class="note-bar note-bar-info"></div><div class="note-body">Sesja Premium aktywna ✓ &nbsp;|&nbsp; Sprawdzane spółki: portfel + watchlista</div></div>', unsafe_allow_html=True)

    # Load alerts state
    if os.path.exists(ALERTS_PATH):
        try:
            with open(ALERTS_PATH, "r", encoding="utf-8") as f:
                alerts_state = json.load(f)
        except Exception:
            alerts_state = {"seen_ids": [], "articles": []}
    else:
        alerts_state = {"seen_ids": [], "articles": []}

    # Build combined ticker list: portfolio + watchlist
    alert_tickers = list(set(watchlist))
    if os.path.exists(HOLDINGS_PATH):
        try:
            df_h = pd.read_csv(HOLDINGS_PATH)
            for t in df_h["Spółka"].tolist():
                if t not in alert_tickers:
                    alert_tickers.append(t)
        except Exception:
            pass

    _section_divider()
    check_clicked = st.button("🔍 Sprawdź nowe analizy", use_container_width=True, type="primary", disabled=not has_cookie)
    with st.expander(f"📋 Obserwowane spółki ({len(alert_tickers)})", expanded=False):
        _cols_a = st.columns(5)
        for _i, _t in enumerate(sorted(alert_tickers)):
            _cols_a[_i % 5].markdown(f"`{_t}`")

    if check_clicked and has_cookie:
        with st.spinner("Pobieram analizy ze Stockwatch Premium..."):
            scraper_alerts = StockwatchScraper(phpsessid=settings.get("phpsessid", ""))
            new_articles, error_msg = scraper_alerts.get_new_analyses(
                tickers=alert_tickers,
                seen_ids=alerts_state.get("seen_ids", []),
                pages=3
            )
        if error_msg:
            st.error(error_msg)
        elif not new_articles:
            st.success("Brak nowych analiz — wszystkie już widziane.")
        else:
            # Merge new into history
            all_articles = new_articles + alerts_state.get("articles", [])
            all_seen = list({a["id"] for a in all_articles})
            alerts_state = {"seen_ids": all_seen, "articles": all_articles[:200]}
            with open(ALERTS_PATH, "w", encoding="utf-8") as f:
                json.dump(alerts_state, f, ensure_ascii=False, indent=2)
            st.success(f"Znaleziono **{len(new_articles)}** nowych analiz!")
            st.rerun()

    _section_divider()

    # Display stored articles
    all_stored = alerts_state.get("articles", [])
    if not all_stored:
        st.markdown('<div class="note-card"><div class="note-bar note-bar-info"></div><div class="note-body">Brak zapisanych alertów. Kliknij <b>Sprawdź nowe analizy</b> (wymaga ciasteczka Premium).</div></div>', unsafe_allow_html=True)
    else:
        # Filter controls
        col_f1, col_f2 = st.columns([1, 1])
        with col_f1:
            kind_filter = st.selectbox("Typ analizy", ["Wszystkie", "Analiza techniczna", "Analiza fundamentalna", "Artykuł / komentarz"])
        with col_f2:
            ticker_filter = st.multiselect("Spółka", sorted({a["ticker"] for a in all_stored}))

        filtered = [
            a for a in all_stored
            if (kind_filter == "Wszystkie" or a["kind"] == kind_filter)
            and (not ticker_filter or a["ticker"] in ticker_filter)
        ]

        st.markdown(f"**{len(filtered)}** alertów")

        # Render articles as UXR note cards
        for art in filtered[:50]:
            kind_bar = "note-bar-info" if "technicz" in art["kind"].lower() else ("note-bar-warn" if "fundamental" in art["kind"].lower() else "note-bar-info")
            date_badge = f'<span style="font-size:10px;color:#808080;margin-left:8px;">{art["date"]}</span>' if art["date"] else ""
            ticker_badge = f'<span style="background:#131f33;color:#ecfa64;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;margin-right:6px;">{art["ticker"]}</span>'
            kind_badge = f'<span style="border:1.5px solid {art["kind_color"]};color:{art["kind_color"]};padding:1px 7px;border-radius:4px;font-size:10px;font-weight:600;">{art["kind"]}</span>'
            link = f'<a href="{art["url"]}" target="_blank" style="color:#5B8DEF;font-size:12px;font-weight:500;text-decoration:none;">Otwórz ↗</a>'
            st.markdown(f"""
            <div class="note-card">
              <div class="note-bar {kind_bar}"></div>
              <div class="note-body">
                {ticker_badge}{kind_badge}{date_badge}<br>
                <span style="font-size:13px;color:#1a1a1a;">{art["title"]}</span>
                &nbsp;&nbsp;{link}
              </div>
            </div>
            """, unsafe_allow_html=True)

        if len(filtered) > 50:
            st.caption(f"Pokazano 50 z {len(filtered)} alertów.")

        col_clear, _ = st.columns([1, 3])
        with col_clear:
            if st.button("🗑️ Wyczyść historię alertów", use_container_width=True):
                alerts_state = {"seen_ids": [], "articles": []}
                with open(ALERTS_PATH, "w", encoding="utf-8") as f:
                    json.dump(alerts_state, f)
                st.rerun()

# ==========================================
# TAB 5: REKOMENDACJA NOWYCH INWESTYCJI
# ==========================================

def _horizon_score(item, horizon_label):
    s_cz, s_cwk, s_ev, s_dy = _comp_scores(
        item.get("c_z"), item.get("c_wk"), item.get("ev_ebitda"), item.get("dy")
    )
    trend = float(item.get("trend_score") or 70)
    if "3" in horizon_label:
        return round(0.15 * s_cz + 0.10 * s_cwk + 0.10 * s_ev + 0.05 * s_dy + 0.60 * trend, 1)
    elif "12" in horizon_label:
        return round(0.25 * s_cz + 0.25 * s_cwk + 0.15 * s_ev + 0.20 * s_dy + 0.15 * trend, 1)
    else:
        return float(item.get("score", 50))


def _build_rationale(item, horizon_label):
    parts = []
    c_z = item.get("c_z")
    c_wk = item.get("c_wk")
    dy = item.get("dy")
    trend = item.get("trend_score", 70)
    if c_z is not None and 5 <= c_z <= 20:
        parts.append(f"Atrakcyjna wycena C/Z = {c_z:.1f}")
    if c_wk is not None and c_wk <= 2.5:
        parts.append(f"C/WK = {c_wk:.2f} (niedowartościowane względem księgowej)")
    if dy and dy >= 2.0:
        parts.append(f"Dywidenda {dy:.1f}% rocznie")
    if trend >= 75:
        parts.append("Trend wzrostowy powyżej SMA50")
    if "3" in horizon_label:
        parts.append("Krótki horyzont: priorytet impulsu cenowego")
    elif "12" in horizon_label:
        parts.append("Długi horyzont: solidne fundamenty i dywidenda")
    return " · ".join(parts) if parts else "Ogólna atrakcyjność wg modelu punktowego"


with tab5:
    st.header("💰 Rekomendacja Nowych Inwestycji")
    _portfolio_badge()
    st.markdown("Analiza, w co i dlaczego warto zainwestować nowy kapitał. Uwzględnia bieżące wagi portfela i nie rekomenduje spółek przekraczających limit 15%.")

    _is_ikze = selected_portfolio == "ikze"
    if _is_ikze:
        invest_amount = st.selectbox("Kwota inwestycji", [500, 1000, 2000, 5000], format_func=lambda x: f"{x:,} PLN")
        invest_horizon = "12 miesięcy (długi)"
        st.markdown('<div class="note-card"><div class="note-bar" style="background:#34d399;"></div><div class="note-body" style="font-size:12px;">🔒 <b>IKE/IKZE</b> — horyzont długoterminowy (25 lat). Kup i trzymaj do 2051 — zyski kapitałowe <b>tax-free</b> przy wypłacie z IKE/IKZE.</div></div>', unsafe_allow_html=True)
    else:
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            invest_amount = st.selectbox("Kwota inwestycji", [1000, 2000, 5000], format_func=lambda x: f"{x:,} PLN")
        with col_a2:
            invest_horizon = st.selectbox("Horyzont inwestycji", ["3 miesiące (krótki)", "6 miesięcy (średni)", "12 miesięcy (długi)"])

    if st.button("🔍 Analizuj i Doradź", type="primary", use_container_width=True):
        recom_data = st.session_state.get("recommendations_data")
        if not recom_data:
            with st.spinner("Pobieranie danych z Biznesradar / Yahoo Finance..."):
                scraper_inv = StockwatchScraper(phpsessid=settings.get("phpsessid", ""))
                with open(WATCHLIST_PATH, "r") as _f:
                    wl_inv = json.load(_f)
                recom_data = []
                for _ticker in wl_inv:
                    _ind = scraper_inv.get_indicators(_ticker)
                    _trend = scraper_inv.get_technical_trend(_ticker)
                    _score = calculate_portfolio_score(_ind, _trend, selected_portfolio)
                    _recom = scraper_inv.get_recommendation(_score)
                    recom_data.append({
                        "ticker": _ticker,
                        "c_z": _ind.get("c_z"),
                        "c_wk": _ind.get("c_wk"),
                        "ev_ebitda": _ind.get("ev_ebitda"),
                        "dy": _ind.get("dy"),
                        "price": _ind.get("price"),
                        "trend_score": _trend,
                        "score": _score,
                        "action": _recom["action"],
                        "color": _recom["color"],
                        "text_color": _recom["text_color"],
                        "source": _ind.get("source", ""),
                    })
                st.session_state["recommendations_data"] = recom_data

        # Current portfolio allocation
        if os.path.exists(HOLDINGS_PATH):
            _df_h = pd.read_csv(HOLDINGS_PATH)
            _live = st.session_state.get("live_prices", {})
            _vals = {}
            for _, _row in _df_h.iterrows():
                _p = float(_live.get(_row["Spółka"], _row["Kurs (PLN)"]))
                _vals[_row["Spółka"]] = int(_row["Ilość"]) * _p
            _total_val = sum(_vals.values()) or 1.0
            _current_alloc_pct = {t: v / _total_val * 100 for t, v in _vals.items()}
        else:
            _current_alloc_pct = {}
            _total_val = 100000.0

        # Score candidates
        candidates = []
        for item in recom_data:
            score_adj = _horizon_score(item, invest_horizon)
            cur_pct = _current_alloc_pct.get(item["ticker"], 0.0)
            price = float(item.get("price") or 0)
            if score_adj < 55 or cur_pct >= 14.0 or price <= 0:
                continue
            candidates.append({**item, "score_adj": score_adj, "current_pct": cur_pct, "price": price})

        candidates.sort(key=lambda x: x["score_adj"], reverse=True)

        # IKE/IKZE: if ETF allocation < 60%, bubble ETF tickers to the top
        if _is_ikze:
            _etf_val = sum(v for t, v in (_vals if os.path.exists(HOLDINGS_PATH) else {}).items() if t in ETF_TICKERS)
            _total_ikze = _total_val if _total_val > 1 else 1.0
            _etf_pct = _etf_val / _total_ikze * 100
            if _etf_pct < 60.0:
                etf_cands = [c for c in candidates if c["ticker"] in ETF_TICKERS]
                other_cands = [c for c in candidates if c["ticker"] not in ETF_TICKERS]
                candidates = etf_cands + other_cands

        top3 = candidates[:3]

        if not top3:
            st.warning("Brak kandydatów spełniających kryteria. Uruchom analizę w Tab 1 lub zmień horyzont.")
        else:
            total_score_sum = sum(c["score_adj"] for c in top3) or 1.0
            for c in top3:
                c["alloc_pln"] = invest_amount * (c["score_adj"] / total_score_sum)
                c["shares"] = int(c["alloc_pln"] / c["price"])
                c["actual_pln"] = c["shares"] * c["price"]
                c["new_pct"] = c["current_pct"] + (c["actual_pln"] / _total_val * 100)
                if _is_ikze and c["ticker"] in ETF_TICKERS:
                    c["rationale"] = "Kup i trzymaj do 2051 — tax-free przy wypłacie z IKE/IKZE. ETF reinwestuje dywidendy wewnętrznie bez podatku."
                elif _is_ikze:
                    c["rationale"] = _build_rationale(c, invest_horizon) + " · Strategia wzrostowa IKE/IKZE (bez podatku Belki)"
                else:
                    c["rationale"] = _build_rationale(c, invest_horizon)

            st.session_state["invest_result"] = {
                "amount": invest_amount,
                "horizon": invest_horizon,
                "candidates": top3,
                "total_val": _total_val,
                "is_ikze": _is_ikze,
            }
            st.rerun()

    if "invest_result" in st.session_state:
        res = st.session_state["invest_result"]
        candidates_res = res["candidates"]
        total_val_res = res["total_val"]

        st.markdown(f"""
        <div class="note-card">
          <div class="note-bar note-bar-info"></div>
          <div class="note-body" style="font-size:12px;">
            <b>Kwota:</b> {res['amount']:,} PLN &nbsp;|&nbsp; <b>Horyzont:</b> {"25 lat (IKE/IKZE — tax-free)" if res.get('is_ikze') else res['horizon']} &nbsp;|&nbsp;
            <b>Kandydaci:</b> {len(candidates_res)} spółek
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="uxr-subheader"><div class="uxr-subheader-bar"></div><div class="uxr-subheader-text">🏆 Top Rekomendacje</div></div>', unsafe_allow_html=True)

        for rank, c in enumerate(candidates_res, 1):
            action_color = c.get("color", "#FFC107")
            action_text_color = c.get("text_color", "#212529")
            action_label = c.get("action", "TRZYMAJ")
            score_adj = c["score_adj"]
            price = c["price"]
            shares = c["shares"]
            actual_pln = c["actual_pln"]
            new_pct = c["new_pct"]
            cur_pct = c["current_pct"]
            rationale = c["rationale"]
            ticker = c["ticker"]

            medal = ["🥇", "🥈", "🥉"][rank - 1]

            dy_str = f"{c['dy']:.1f}%" if c.get("dy") else "—"
            cz_str = f"{c['c_z']:.1f}" if c.get("c_z") else "—"
            cwk_str = f"{c['c_wk']:.2f}" if c.get("c_wk") else "—"

            st.markdown(f"""
            <div class="note-card" style="margin-bottom:16px;">
              <div class="note-bar" style="background:{action_color};"></div>
              <div class="note-body">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
                  <div>
                    <span style="font-size:22px;font-weight:700;color:#131f33;">{medal} {ticker}</span>
                    &nbsp;
                    <span style="background:{action_color};color:{action_text_color};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">{action_label}</span>
                  </div>
                  <div style="text-align:right;">
                    <span style="font-size:20px;font-weight:700;color:#131f33;">{actual_pln:,.2f} zł</span>
                    <span style="font-size:13px;color:#666;margin-left:6px;">({shares} szt. × {price:,.2f} zł)</span>
                  </div>
                </div>
                <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:13px;margin-bottom:10px;">
                  <div><span style="color:#666;">Score (horyzont):</span> <b style="color:#131f33;">{score_adj:.1f}/100</b></div>
                  <div><span style="color:#666;">C/Z:</span> <b>{cz_str}</b></div>
                  <div><span style="color:#666;">C/WK:</span> <b>{cwk_str}</b></div>
                  <div><span style="color:#666;">DY:</span> <b>{dy_str}</b></div>
                  <div><span style="color:#666;">Udział przed:</span> <b>{cur_pct:.1f}%</b></div>
                  <div><span style="color:#{'dc2626' if new_pct > 12 else '16a34a'};">Udział po:</span> <b>{new_pct:.1f}%</b></div>
                </div>
                <div style="font-size:12px;color:#444;border-top:1px solid #f0f0f0;padding-top:8px;">
                  💡 {rationale}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # Summary table
        with st.expander("📋 Podsumowanie alokacji nowego kapitału"):
            summary_rows = []
            total_actual = sum(c["actual_pln"] for c in candidates_res)
            leftover = res["amount"] - total_actual
            for c in candidates_res:
                summary_rows.append({
                    "Spółka": c["ticker"],
                    "Akcji": c["shares"],
                    "Cena (PLN)": f"{c['price']:,.2f}",
                    "Koszt (PLN)": f"{c['actual_pln']:,.2f}",
                    "Udział po (%)": f"{c['new_pct']:.1f}%",
                    "Score": c["score_adj"],
                })
            df_summary = pd.DataFrame(summary_rows)
            st.dataframe(df_summary, use_container_width=True, hide_index=True)
            st.markdown(f"**Łączny koszt:** {total_actual:,.2f} PLN &nbsp;|&nbsp; **Reszta:** {leftover:,.2f} PLN (zostaje na rachunku)")

        if st.button("🔄 Wyczyść wynik i analizuj ponownie"):
            del st.session_state["invest_result"]
            st.rerun()
