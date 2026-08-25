import streamlit as st
import pandas as pd
import plotly.express as px
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

# Custom styling for rich aesthetics and clean mobile looks
st.markdown("""
<style>
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #0066CC;
        margin-bottom: 10px;
        min-height: 110px;
    }
    .metric-title {
        font-size: 13px;
        color: #6C757D;
        font-weight: bold;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 22px;
        color: #212529;
        font-weight: bold;
    }
    .metric-delta {
        font-size: 13px;
        font-weight: bold;
    }
    .delta-plus {
        color: #28A745;
    }
    .delta-minus {
        color: #DC3545;
    }
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
st.sidebar.subheader("🔑 Autoryzacja Stockwatch")
new_phpsessid = st.sidebar.text_input(
    "Ciasteczko PHPSESSID",
    value=settings.get("phpsessid", ""),
    type="password",
    help="Wpisz wartość ciasteczka PHPSESSID z zalogowanej sesji na Stockwatch.pl, aby pobierać najświeższe wskaźniki giełdowe."
)

if new_phpsessid != settings.get("phpsessid", ""):
    settings["phpsessid"] = new_phpsessid
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)
    st.rerun()

# TAB NAVIGATION
tab1, tab2, tab3 = st.tabs([
    "☀️ Rekomendacje 8:00", 
    "🎯 Strategia", 
    "📊 Wyniki i Portfel"
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

    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if st.button("🔄 Uruchom Analizę Rekomendacji", use_container_width=True, type="primary"):
            with st.spinner("Pobieranie i analiza wskaźników z portalów Stockwatch i Yahoo..."):
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
                st.success("Analiza wskaźnikowa zakończona pomyślnie!")
                st.rerun()

    with col_info:
        st.markdown(f"""
        * **Watchlist:** `{', '.join(watchlist)}`
        * **Ciasteczko PHPSESSID:** {"🔑 Podane (L1 Premium Aktywne)" if settings.get("phpsessid") else "⚠️ Brak (L2/L3 Fallback)"}
        * **Wagi modelu:** C/Z (30%), C/WK (20%), EV/EBITDA (20%), Dywidenda (10%), Trend SMA50 (20%)
        """)

    st.markdown("---")

    if st.session_state["recommendations_data"] is not None:
        recom_list = st.session_state["recommendations_data"]
        
        # HTML Table for rich aesthetics
        html_table = """
        <table style="width:100%; border-collapse: collapse; margin-top: 10px; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <thead>
                <tr style="background-color: #0F1D36; color: #FFFFFF; font-weight: bold; border-bottom: 3px solid #0066CC; text-align: left;">
                    <th style="padding: 12px; font-size: 13px;">Spółka</th>
                    <th style="padding: 12px; font-size: 13px;">Kurs Bieżący</th>
                    <th style="padding: 12px; font-size: 13px; text-align: center;">C/Z</th>
                    <th style="padding: 12px; font-size: 13px; text-align: center;">C/WK</th>
                    <th style="padding: 12px; font-size: 13px; text-align: center;">EV/EBITDA</th>
                    <th style="padding: 12px; font-size: 13px; text-align: center;">Dywidenda</th>
                    <th style="padding: 12px; font-size: 13px;">Trend SMA50</th>
                    <th style="padding: 12px; font-size: 13px; text-align: center;">Score</th>
                    <th style="padding: 12px; font-size: 13px; text-align: center;">Rekomendacja</th>
                    <th style="padding: 12px; font-size: 12px; text-align: center;">Źródło</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for row in recom_list:
            cz_val = f"{row['c_z']:.2f}" if row['c_z'] is not None and row['c_z'] != 0 else ("Strata" if row['c_z'] is not None and row['c_z'] < 0 else "N/A")
            cwk_val = f"{row['c_wk']:.2f}" if row['c_wk'] is not None else "N/A"
            ev_val = f"{row['ev_ebitda']:.2f}" if row['ev_ebitda'] is not None else "N/A"
            dy_val = f"{row['dy']:.2f}%" if row['dy'] is not None and row['dy'] > 0 else "0.00%"
            price_val = f"{row['price']:,.2f} zł" if row['price'] is not None else "N/A"
            trend_label = "📈 Wzrostowy" if row['trend_score'] == 100 else "📉 Spadkowy/Konsol."
            trend_color = "#28A745" if row['trend_score'] == 100 else "#DC3545"
            
            src_color = "#6F42C1" if "Premium" in row['source'] else ("#0066CC" if "Yahoo" in row['source'] else "#6C757D")
            
            html_table += f"""
                <tr style="border-bottom: 1px solid #E2E2E2; font-size: 13px; font-weight: 500; color: #212529;">
                    <td style="padding: 12px; font-weight: bold; color: #0F1D36;">{row['ticker']}</td>
                    <td style="padding: 12px; font-weight: bold;">{price_val}</td>
                    <td style="padding: 12px; text-align: center;">{cz_val}</td>
                    <td style="padding: 12px; text-align: center;">{cwk_val}</td>
                    <td style="padding: 12px; text-align: center;">{ev_val}</td>
                    <td style="padding: 12px; text-align: center; color: #28A745; font-weight: bold;">{dy_val}</td>
                    <td style="padding: 12px; color: {trend_color}; font-weight: bold;">{trend_label}</td>
                    <td style="padding: 12px; text-align: center; font-weight: bold; font-size: 14px; color: #0F1D36;">{row['score']:.1f}</td>
                    <td style="padding: 12px; text-align: center;">
                        <span style="background-color: {row['color']}; color: {row['text_color']}; padding: 6px 12px; border-radius: 20px; font-size: 10px; font-weight: bold; display: inline-block; min-width: 80px; text-align: center;">{row['action']}</span>
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        <span style="border: 1px solid {src_color}; color: {src_color}; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: bold;">{row['source']}</span>
                    </td>
                </tr>
            """
            
        html_table += "</tbody></table>"
        st.markdown(html_table, unsafe_allow_html=True)
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
            "KRUK": "Finanse i Windykacja",
            "LPP": "Odzież i Handel",
            "GRODNO": "Elektrotechnika i OZE",
            "RYVU": "Biotechnologia i Medycyna",
            "SYNEKTIK": "Biotechnologia i Medycyna",
            "MODIVO": "Odzież i Handel",
            "NEWAG": "Przemysł i Transport",
            "GPW": "Finanse i Windykacja",
            "SEKO": "Przemysł Spożywczy",
            "DOMDEV": "Budownictwo i Deweloperzy",
            "XTB": "Finanse i Windykacja",
            "ETFBW20TR": "Fundusze ETF",
            "SYN2BIO": "Biotechnologia i Medycyna",
            "KOLEJKOWO": "Rozrywka i Turystyka",
            "DEKPOL": "Budownictwo i Deweloperzy",
            "ETFBSPXPL": "Fundusze ETF",
            "PKOBP": "Finanse i Windykacja",
            "LUBAWA": "Przemysł i Obrona",
            "PKPCARGO": "Przemysł i Transport",
            "ZREMB": "Przemysł i Maszyny",
            "KLEPSYDRA": "Usługi",
            "RANKPROGR": "Budownictwo i Deweloperzy",
            "STAPORKOW": "Przemysł i Konstrukcje",
            "GETIN": "Finanse i Windykacja"
        }

        # Initialize live prices from the holdings CSV (which represents purchase cost basis)
        if "live_prices" not in st.session_state or not st.session_state["live_prices"]:
            st.session_state["live_prices"] = {row["Spółka"]: row["Kurs (PLN)"] for _, row in df_holdings.iterrows()}

        col_ref, col_lbl = st.columns([1, 2])
        with col_ref:
            if st.button("🔄 Odśwież Kursy Bieżące (Yahoo Finance)", use_container_width=True):
                with st.spinner("Pobieranie aktualnych notowań..."):
                    live_prices = {}
                    for ticker in df_holdings["Spółka"].unique():
                        symbol = YFIN_TICKERS.get(ticker, f"{ticker}.WA")
                        try:
                            yft = yf.Ticker(symbol)
                            hist = yft.history(period="1d")
                            if not hist.empty:
                                live_prices[ticker] = float(hist["Close"].iloc[-1])
                            else:
                                live_prices[ticker] = float(df_holdings.loc[df_holdings["Spółka"] == ticker, "Kurs (PLN)"].values[0])
                        except Exception:
                            live_prices[ticker] = float(df_holdings.loc[df_holdings["Spółka"] == ticker, "Kurs (PLN)"].values[0])
                    st.session_state["live_prices"] = live_prices
                    st.success("Zaktualizowano kursy!")
                    st.rerun()
        with col_lbl:
            st.markdown(f"""
            * **Limit alokacji spółki:** `max 15.0%`
            * **Limit alokacji sektora:** `max 30.0%`
            * **Zabezpieczenie:** Stop-Loss (`-10.0%`) | Take-Profit Trailing (`+25.0%`)
            """)

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
            st.markdown("### ⚠️ Ostrzeżenia Alokacyjne (Quality Gate)")
            for warn in allocation_warnings:
                st.markdown(f"<div style='background-color:#FFF3CD; padding:10px 15px; border-radius:5px; border-left:5px solid #FFC107; margin-bottom:8px; font-size:13px; font-weight:500; color:#856404;'>{warn}</div>", unsafe_allow_html=True)
            st.markdown("---")

        # Visual charts (Stock allocation vs Sector allocation)
        col_ch1, col_ch2 = st.columns(2)
        with col_ch1:
            # Stock allocation chart
            fig_stock_alloc = px.bar(
                df_strat.sort_values(by="Udział Bieżący (%)", ascending=True),
                x="Udział Bieżący (%)",
                y="Spółka",
                orientation="h",
                title="Udział Spółek w Portfelu Akcji (%)",
                color="Udział Bieżący (%)",
                color_continuous_scale="Blues"
            )
            # Add limit line
            fig_stock_alloc.add_vline(x=15.0, line_dash="dash", line_color="red", annotation_text="Limit 15%")
            fig_stock_alloc.update_layout(margin=dict(l=10, r=10, t=40, b=10), showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig_stock_alloc, use_container_width=True)

        with col_ch2:
            # Sector allocation chart
            fig_sect_alloc = px.pie(
                df_sect,
                names="Sektor",
                values="Wycena Bieżąca (PLN)",
                hole=0.4,
                title="Udział Sektorów w Portfelu Akcji (%)",
                color_discrete_sequence=px.colors.qualitative.Dark2
            )
            fig_sect_alloc.update_layout(margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_sect_alloc, use_container_width=True)

        # Risk Management (Stop-Loss & Take-Profit)
        st.markdown("### 🛑 Monitor Ryzyka (Stop-Loss & Take-Profit)")
        
        # HTML Risk Table
        risk_table = """
        <table style="width:100%; border-collapse: collapse; margin-top: 10px; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <thead>
                <tr style="background-color: #0F1D36; color: #FFFFFF; font-weight: bold; border-bottom: 3px solid #0066CC; text-align: left;">
                    <th style="padding: 12px; font-size: 13px;">Spółka</th>
                    <th style="padding: 12px; font-size: 13px;">Ilość</th>
                    <th style="padding: 12px; font-size: 13px;">Cena Wejścia (Koszt)</th>
                    <th style="padding: 12px; font-size: 13px;">Kurs Bieżący</th>
                    <th style="padding: 12px; font-size: 13px;">Wynik (%)</th>
                    <th style="padding: 12px; font-size: 13px; text-align: center;">Status Zlecenia / Alert</th>
                </tr>
            </thead>
            <tbody>
        """

        for _, r in df_strat.iterrows():
            purchase = r["Kurs (PLN)"]
            current = r["Kurs Bieżący (PLN)"]
            change_pct = ((current - purchase) / purchase) * 100 if purchase > 0 else 0.0
            
            # Formatting and styling
            change_str = f"{change_pct:+.2f}%"
            change_color = "#28A745" if change_pct >= 0 else "#DC3545"
            
            if change_pct <= -10.0:
                status_badge = '<span style="background-color: #DC3545; color: #FFFFFF; padding: 6px 12px; border-radius: 20px; font-size: 10px; font-weight: bold; display: inline-block; min-width: 140px; text-align: center;">🛑 STOP-LOSS TRIGGERED!</span>'
            elif change_pct >= 25.0:
                status_badge = '<span style="background-color: #28A745; color: #FFFFFF; padding: 6px 12px; border-radius: 20px; font-size: 10px; font-weight: bold; display: inline-block; min-width: 140px; text-align: center;">🟢 TAKE-PROFIT ACTIVE!</span>'
            else:
                status_badge = '<span style="background-color: #17A2B8; color: #FFFFFF; padding: 6px 12px; border-radius: 20px; font-size: 10px; font-weight: bold; display: inline-block; min-width: 140px; text-align: center;">⚪ OK (Zabezpieczone)</span>'

            risk_table += f"""
                <tr style="border-bottom: 1px solid #E2E2E2; font-size: 13px; font-weight: 500; color: #212529;">
                    <td style="padding: 12px; font-weight: bold; color: #0F1D36;">{r['Spółka']}</td>
                    <td style="padding: 12px;">{r['Ilość']:,}</td>
                    <td style="padding: 12px;">{purchase:,.2f} zł</td>
                    <td style="padding: 12px; font-weight: bold;">{current:,.2f} zł</td>
                    <td style="padding: 12px; color: {change_color}; font-weight: bold; font-size: 14px;">{change_str}</td>
                    <td style="padding: 12px; text-align: center;">{status_badge}</td>
                </tr>
            """
            
        risk_table += "</tbody></table>"
        st.markdown(risk_table, unsafe_allow_html=True)

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
        
        # Display KPIs using custom HTML for beautiful mobile-first design (5 columns)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Wycena Portfela ({latest_date})</div>
                <div class="metric-value">{latest_val:,.2f} PLN</div>
                <div class="metric-delta {daily_delta_class}">Sesja: {daily_change_pln:+.2f} PLN</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #28A745;">
                <div class="metric-title">Wynik Ostatniego Dnia</div>
                <div class="metric-value">{daily_change_pln:+.2f} PLN</div>
                <div class="metric-delta {daily_delta_class}">{daily_delta_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Skumulowany Zysk Netto</div>
                <div class="metric-value">{total_change_pct:+.2f}%</div>
                <div class="metric-delta {total_delta_class}">{total_delta_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #6F42C1;">
                <div class="metric-title">Suma Wpłat (od Q1 2026)</div>
                <div class="metric-value">{latest_deposits:,.2f} PLN</div>
                <div class="metric-delta" style="color: #6C757D;">Kapitał zewnętrzny</div>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #FFC107;">
                <div class="metric-title">Gotówka w Portfelu</div>
                <div class="metric-value">{latest_cash:,.2f} PLN</div>
                <div class="metric-delta" style="color: #6C757D;">Wolne środki</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Brak danych historycznych. Wgraj raport PDF lub wykaz instrumentów, aby wygenerować metryki.")

    st.markdown("---")

    # 3. WYKRES EWOLUCJI PORTFELA W CZASIE (TRZYWYMIAROWY: WARTOŚĆ vs ZYSK vs WPŁATY)
    if not df_history.empty:
        st.subheader("Ewolucja Portfela, Zysku i Sumy Wpłat")
        
        # Melt dataframe to make it suitable for Plotly Express multi-line
        df_plot = df_history.melt(
            id_vars=["Data"],
            value_vars=["Wartość Całkowita (PLN)", "Zysk (PLN)", "Wpłaty Skumulowane (PLN)"],
            var_name="Wskaźnik",
            value_name="Wartość (PLN)"
        )
        
        # Plotly multi-line chart
        fig = px.line(
            df_plot, 
            x="Data", 
            y="Wartość (PLN)",
            color="Wskaźnik",
            title="Ewolucja Wartości Portfela vs Zysk Organiczny vs Suma Wpłat (Od Q1 2026)",
            markers=True,
            color_discrete_map={
                "Wartość Całkowita (PLN)": "#0066CC",
                "Zysk (PLN)": "#28A745",
                "Wpłaty Skumulowane (PLN)": "#6F42C1"
            }
        )
        fig.update_layout(
            hovermode="x unified", 
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_title="Data",
            yaxis_title="Wartość (PLN)",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(gridcolor='#E2E2E2'),
            xaxis=dict(gridcolor='#E2E2E2')
        )
        st.plotly_chart(fig, use_container_width=True)
        
    # 4. STRUCTURA I SKŁAD PORTFELA
    st.subheader("Skład i Struktura Portfela")
    
    if os.path.exists(HOLDINGS_PATH):
        df_holdings = pd.read_csv(HOLDINGS_PATH)
    else:
        df_holdings = pd.DataFrame()
        
    if not df_holdings.empty:
        col_pie, col_table = st.columns([2, 3])
        
        with col_pie:
            # Pie chart for portfolio structure
            df_pie = df_holdings.copy()
            df_pie.loc[df_pie['Udział (%)'] < 2.5, 'Spółka'] = 'Inne'
            
            fig_pie = px.pie(
                df_pie, 
                names="Spółka", 
                values="Wycena (PLN)", 
                hole=0.4,
                title="Struktura Portfela",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_layout(margin=dict(l=10, r=10, t=40, b=10))
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
