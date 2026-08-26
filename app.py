import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import tempfile
import json
import yfinance as yf
from src.pdf_parser import parse_erste_pdf
from src.stockwatch_scraper import StockwatchScraper, YFIN_TICKERS

# Set page config for mobile friendliness
st.set_page_config(
    page_title="GPW Erste Portfolio",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Resolve paths dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, "data", "portfolio_history.csv")
HOLDINGS_PATH = os.path.join(BASE_DIR, "data", "current_holdings.csv")
SETTINGS_PATH = os.path.join(BASE_DIR, "data", "portfolio_settings.json")
DEPOSIT_HISTORY_PATH = os.path.join(BASE_DIR, "data", "deposit_history.json")

# Create data directory if it doesn't exist
os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)

# Load settings for cumulative external deposits and Stockwatch session
if os.path.exists(SETTINGS_PATH):
    try:
        with open(SETTINGS_PATH, "r") as f:
            settings = json.load(f)
    except Exception:
        settings = {"total_deposits": 107466.94, "phpsessid": ""}
else:
    settings = {"total_deposits": 107466.94, "phpsessid": ""}
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)

if "phpsessid" not in settings:
    settings["phpsessid"] = ""

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
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ecfa64 !important; font-size: 14px !important; letter-spacing: 0.5px;
    }
    [data-testid="stSidebar"] label { color: rgba(255,255,255,0.6) !important; font-size: 12px !important; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.1) !important; }
    [data-testid="stSidebar"] input {
        background: #1f2b40 !important; color: #fff !important;
        border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 6px !important;
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
        width: 100% !important;
    }
    .stButton > button:hover { background-color: #cde200 !important; }

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

# ==========================================
# SIDEBAR - PORTFOLIO CONFIGURATION
# ==========================================
st.sidebar.header("⚙️ Zarządzanie Kapitałem")
st.sidebar.markdown("Ustawienia wpłat zewnętrznych w celu wyliczenia **realnego zysku organicznego** (bez wpływu dopłat środków).")

new_total_deposits = st.sidebar.number_input(
    "Suma wpłat zewnętrznych (PLN)",
    value=float(settings["total_deposits"]),
    step=500.0,
    help="Wpisz sumę wszystkich fizycznych wpłat na konto maklerskie z zewnątrz. Zysk będzie wyliczany jako: Wartość Portfela - Suma Wpłat.",
    format="%.2f"
)

# Save settings and dynamically recalculate latest profit if deposits changed
if new_total_deposits != settings["total_deposits"]:
    settings["total_deposits"] = new_total_deposits
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)
    
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
<div style="font-size:11px;color:rgba(255,255,255,0.55);line-height:1.6;margin-bottom:8px;">
Stockwatch.pl używa <b style="color:#ecfa64;">ASP.NET_SessionId</b> — nie PHPSESSID.<br><br>
<b>Jak znaleźć:</b><br>
① Zaloguj się na stockwatch.pl<br>
② DevTools (F12) → <b>Application</b><br>
③ Cookies → <b>https://www.stockwatch.pl</b><br>
④ Skopiuj wartość <b>ASP.NET_SessionId</b><br><br>
<i>Alternatywnie: Network → dowolny request → Request Headers → Cookie</i>
</div>
""", unsafe_allow_html=True)
new_phpsessid = st.sidebar.text_input(
    "ASP.NET_SessionId (cookie sesji)",
    value=settings.get("phpsessid", ""),
    type="password",
    help="Wartość ciasteczka ASP.NET_SessionId z zalogowanej sesji Premium na stockwatch.pl. Bez niego dane pobierane są z Yahoo Finance lub lokalnej bazy (L2/L3)."
)

if new_phpsessid != settings.get("phpsessid", ""):
    settings["phpsessid"] = new_phpsessid
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)
    st.rerun()

ALERTS_PATH = os.path.join(BASE_DIR, "data", "stockwatch_alerts.json")

# TAB NAVIGATION
tab1, tab2, tab3, tab4 = st.tabs([
    "☀️ Rekomendacje 8:00",
    "🎯 Strategia",
    "📊 Wyniki i Portfel",
    "🔔 Alerty Stockwatch",
])

# ==========================================
# TAB 1 & 2: REKOMENDACJE I STRATEGIA
# ==========================================
with tab1:
    st.header("☀️ Rekomendacje Sesyjne (Stockwatch 8:00)")
    st.markdown("System pobierania i wieloczynnikowej analizy wskaźników giełdowych przed otwarciem sesji o 9:00.")

    WATCHLIST_PATH = os.path.join(BASE_DIR, "config", "watchlist.json")
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
        <b>Źródło danych:</b> {source_status} &nbsp;|&nbsp; <b>Model:</b> C/Z 30% · C/WK 20% · EV/EBITDA 20% · DY 10% · Trend 20%
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Uruchom Analizę", use_container_width=True, type="primary"):
        with st.spinner("Pobieranie wskaźników..."):
            scraper = StockwatchScraper(phpsessid=settings.get("phpsessid", ""))
            recom_data = []
            for ticker in watchlist:
                indicators = scraper.get_indicators(ticker)
                trend_score = scraper.get_technical_trend(ticker)
                score = scraper.calculate_score(indicators, trend_score)
                recom = scraper.get_recommendation(score)
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
    st.markdown("Nadzór nad limitami alokacji kapitału oraz kontrola ryzyka (Stop-Loss / Take-Profit).")

    if os.path.exists(HOLDINGS_PATH):
        df_holdings = pd.read_csv(HOLDINGS_PATH)
    else:
        df_holdings = pd.DataFrame()

    if df_holdings.empty:
        st.info("Najpierw wgraj raport wyciągu PDF z Erste BM w zakładce 'Wyniki i Portfel', aby załadować pozycje.")
    else:
        SECTORS_MAPPING = {
            "KRUK":      "Finanse i Windykacja",
            "XTB":       "Finanse i Windykacja",
            "PKOBP":     "Finanse i Windykacja",
            "GPW":       "Finanse i Windykacja",
            "GETIN":     "Finanse i Windykacja",
            "LPP":       "Odzież i Handel",
            "MODIVO":    "Odzież i Handel",
            "RAINBOW":   "Rozrywka i Turystyka",
            "KOLEJKOWO": "Rozrywka i Turystyka",
            "GRODNO":    "Elektrotechnika i OZE",
            "RYVU":      "Biotechnologia i Medycyna",
            "SYNEKTIK":  "Biotechnologia i Medycyna",
            "SYN2BIO":   "Biotechnologia i Medycyna",
            "DOMDEV":    "Budownictwo i Deweloperzy",
            "DEKPOL":    "Budownictwo i Deweloperzy",
            "RANKPROGR": "Budownictwo i Deweloperzy",
            "SEKO":      "Przemysł Spożywczy",
            "NEWAG":     "Przemysł i Transport",
            "PKPCARGO":  "Przemysł i Transport",
            "PKNORLEN":  "Energia i Paliwa",
            "LUBAWA":    "Przemysł i Obrona",
            "ZREMB":     "Przemysł i Maszyny",
            "STAPORKOW": "Przemysł i Maszyny",
            "KLEPSYDRA": "Usługi",
            "ETFBW20TR": "Fundusze ETF",
            "ETFBSPXPL": "Fundusze ETF",
            "PKOBP":     "Finanse i Windykacja",
            "LUBAWA":    "Przemysł i Obrona",
        }

        # Initialize live prices from the holdings CSV (which represents purchase cost basis)
        if "live_prices" not in st.session_state or not st.session_state["live_prices"]:
            st.session_state["live_prices"] = {row["Spółka"]: row["Kurs (PLN)"] for _, row in df_holdings.iterrows()}

        st.markdown("""
        <div class="note-card">
          <div class="note-bar note-bar-info"></div>
          <div class="note-body" style="font-size:12px;">
            Limit spółki: <b>15%</b> &nbsp;|&nbsp; Limit sektora: <b>30%</b> &nbsp;|&nbsp;
            Stop-Loss: <b>−10%</b> &nbsp;|&nbsp; Take-Profit: <b>+25%</b>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔄 Odśwież Kursy (Yahoo Finance)", use_container_width=True):
            with st.spinner("Pobieranie aktualnych notowań..."):
                live_prices = {}
                for ticker in df_holdings["Spółka"].unique():
                    symbol = YFIN_TICKERS.get(ticker)
                    try:
                        if symbol:
                            yft = yf.Ticker(symbol)
                            hist = yft.history(period="1d")
                            if not hist.empty:
                                live_prices[ticker] = float(hist["Close"].iloc[-1])
                                continue
                    except Exception:
                        pass
                    live_prices[ticker] = float(df_holdings.loc[df_holdings["Spółka"] == ticker, "Kurs (PLN)"].values[0])
                st.session_state["live_prices"] = live_prices
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
        
        # Allocation warning checks
        allocation_warnings = []
        for _, r in df_strat.iterrows():
            if r["Udział Bieżący (%)"] > 15.0:
                excess_pln = r["Wycena Bieżąca (PLN)"] - (total_live_stocks_val * 0.15)
                allocation_warnings.append(f"⚠️ **Przekroczenie limitu alokacji spółki ({r['Spółka']}):** Udział wynosi **{r['Udział Bieżący (%)']:.2f}%** (limit 15%). Nadwyżka: **{excess_pln:,.2f} zł**. Sugerowana redukcja.")

        df_sect = df_strat.groupby("Sektor")["Wycena Bieżąca (PLN)"].sum().reset_index()
        df_sect["Udział (%)"] = round((df_sect["Wycena Bieżąca (PLN)"] / total_live_stocks_val) * 100, 2)
        
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
        for _, r in df_strat.iterrows():
            purchase = r["Kurs (PLN)"]
            current = r["Kurs Bieżący (PLN)"]
            change_pct = ((current - purchase) / purchase) * 100 if purchase > 0 else 0.0
            change_str = f"{change_pct:+.2f}%"
            change_color = "#16a34a" if change_pct >= 0 else "#dc2626"

            if change_pct <= -10.0:
                badge = '<span style="background:#dc2626;color:#fff;padding:5px 14px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#128721; STOP-LOSS!</span>'
                row_bg = "#fff5f5"
            elif change_pct >= 25.0:
                badge = '<span style="background:#16a34a;color:#fff;padding:5px 14px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#9989; TAKE-PROFIT!</span>'
                row_bg = "#f0fdf4"
            else:
                badge = '<span style="background:#131f33;color:#ecfa64;padding:5px 14px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">&#9711; OK</span>'
                row_bg = "#ffffff"

            risk_rows_html += f"""
            <tr style="background:{row_bg};">
                <td class="td-company">{r['Spółka']}</td>
                <td class="td-num">{int(r['Ilość']):,}</td>
                <td class="td-num">{purchase:,.2f} zł</td>
                <td class="td-num td-bold">{current:,.2f} zł</td>
                <td style="padding:12px 16px;font-size:14px;font-weight:700;color:{change_color};">{change_str}</td>
                <td class="td-center">{badge}</td>
            </tr>"""

        risk_html = f"""<!DOCTYPE html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            *{{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif;}}
            html,body{{background:#f6f6f6;}}
            .wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;padding:4px;border-radius:10px;}}
            table{{min-width:500px;width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);}}
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
                <th>Wynik (%)</th><th class="th-center">Status</th>
            </tr></thead>
            <tbody>{risk_rows_html}</tbody>
        </table></div></body></html>"""

        risk_height = len(df_strat) * 50 + 60
        components.html(risk_html, height=risk_height, scrolling=False)

# ==========================================
# TAB 3: WYNIKI PORTFELA (CEL 3)
# ==========================================
with tab3:
    st.header("📊 Wyniki Portfela (Erste BM)")
    
    # 1. EXPANDER DO WGRYWANIA PDF
    with st.expander("📥 Wgraj nowy raport kwartalny PDF lub wykaz instrumentów (Erste BM)"):
        uploaded_file = st.file_uploader("Wybierz plik PDF wyciągu", type=["pdf"])
        if uploaded_file is not None:
            # Save uploaded file to temp path
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_path = tmp_file.name
                
            try:
                with st.spinner("Przetwarzanie raportu PDF..."):
                    parsed_data = parse_erste_pdf(tmp_path)
                    
                if parsed_data["report_date"] is not None:
                    rep_date = parsed_data["report_date"]
                    
                    # 1. Update history
                    df_history = pd.read_csv(HISTORY_PATH) if os.path.exists(HISTORY_PATH) else pd.DataFrame(columns=["Data", "Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"])
                    df_history["Data"] = df_history["Data"].astype(str)
                    
                    val = parsed_data["total_value"] if parsed_data["total_value"] is not None else parsed_data["stocks_value"]
                    
                    new_row = {
                        "Data": rep_date,
                        "Wartość Całkowita (PLN)": val,
                        "Wycena Akcji (PLN)": parsed_data["stocks_value"],
                        "Gotówka (PLN)": parsed_data["cash_val"] if "cash_val" in parsed_data else parsed_data.get("cash_value", 0.0),
                        "Wpłaty Skumulowane (PLN)": settings["total_deposits"],
                        "Zysk (PLN)": round(val - settings["total_deposits"], 2)
                    }
                    
                    if rep_date in df_history["Data"].values:
                        df_history.loc[df_history["Data"] == rep_date, ["Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)", "Wpłaty Skumulowane (PLN)", "Zysk (PLN)"]] = [
                            new_row["Wartość Całkowita (PLN)"], new_row["Wycena Akcji (PLN)"], new_row["Gotówka (PLN)"], new_row["Wpłaty Skumulowane (PLN)"], new_row["Zysk (PLN)"]
                        ]
                        st.success(f"Zaktualizowano dane dla raportu z dnia: {rep_date}!")
                    else:
                        df_history = pd.concat([df_history, pd.DataFrame([new_row])], ignore_index=True)
                        df_history = df_history.sort_values(by="Data").reset_index(drop=True)
                        st.success(f"Dodano nowy raport do historii z dnia: {rep_date}!")
                        
                    df_history.to_csv(HISTORY_PATH, index=False)
                    
                    # 2. Update current holdings if available
                    if parsed_data["holdings"]:
                        holdings_list = []
                        total_stocks = parsed_data["stocks_value"] if parsed_data["stocks_value"] else sum(h['valuation'] for h in parsed_data["holdings"])
                        if total_stocks == 0:
                            total_stocks = 1.0
                        for h in parsed_data["holdings"]:
                            share = round((h["valuation"] / total_stocks) * 100, 2)
                            holdings_list.append({
                                "Spółka": h["ticker"],
                                "Ilość": h["quantity"],
                                "Kurs (PLN)": h["price"],
                                "Wycena (PLN)": h["valuation"],
                                "Udział (%)": share
                            })
                        df_new_holdings = pd.DataFrame(holdings_list)
                        df_new_holdings = df_new_holdings.sort_values(by="Wycena (PLN)", ascending=False).reset_index(drop=True)
                        df_new_holdings.to_csv(HOLDINGS_PATH, index=False)
                        st.success("Zaktualizowano aktualną strukturę portfela!")
                    
                    # Trigger rerun to show updated data
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
            daily_delta_str = f"{daily_change_pln:+.2f} zł ({daily_change_pct:+.2f}%) vs wczoraj"
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
            <div class="metric-delta {daily_delta_class}">Sesja: {daily_change_pln:+.2f} PLN</div>
          </div>
          <div class="metric-card" style="border-left-color:#27ae60;">
            <div class="metric-title">Wynik Sesji</div>
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
            <div class="metric-title">Gotówka</div>
            <div class="metric-value">{latest_cash:,.2f} PLN</div>
            <div class="metric-delta" style="color:#808080;">Wolne środki</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Brak danych historycznych. Wgraj raport PDF lub wykaz instrumentów, aby wygenerować metryki.")

    st.markdown("---")

    # 3. WYKRES EWOLUCJI PORTFELA + ZNACZNIKI WPŁAT
    if not df_history.empty:
        st.subheader("Ewolucja Portfela, Zysku i Sumy Wpłat")

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
    st.subheader("Skład i Struktura Portfela")
    
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
        st.markdown(f'<div class="note-card"><div class="note-bar note-bar-info"></div><div class="note-body">Sesja Premium aktywna ✓ &nbsp;|&nbsp; Sprawdzane spółki: portfel + watchlista</div></div>', unsafe_allow_html=True)

    st.markdown("---")

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

    col_btn_a, col_info_a = st.columns([1, 2])
    with col_btn_a:
        check_clicked = st.button("🔍 Sprawdź nowe analizy", use_container_width=True, type="primary", disabled=not has_cookie)
    with col_info_a:
        st.markdown(f"**Obserwowane spółki ({len(alert_tickers)}):** `{', '.join(sorted(alert_tickers))}`")

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

    st.markdown("---")

    # Display stored articles
    all_stored = alerts_state.get("articles", [])
    if not all_stored:
        st.info("Brak zapisanych alertów. Kliknij 'Sprawdź nowe analizy' (wymaga ciasteczka Premium).")
    else:
        # Filter controls
        col_f1, col_f2 = st.columns([1, 2])
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
