import streamlit as st
import pandas as pd
import plotly.express as px
import os
import tempfile
from src.pdf_parser import parse_erste_pdf

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

# Create data directory if it doesn't exist
os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)

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
    }
    .metric-title {
        font-size: 14px;
        color: #6C757D;
        font-weight: bold;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 24px;
        color: #212529;
        font-weight: bold;
    }
    .metric-delta {
        font-size: 14px;
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

# TAB NAVIGATION
tab1, tab2, tab3 = st.tabs([
    "☀️ Rekomendacje 8:00", 
    "🎯 Strategia", 
    "📊 Wyniki i Portfel"
])

# ==========================================
# TAB 1 & 2: PLACEHOLDERS
# ==========================================
with tab1:
    st.header("☀️ Rekomendacje Sesyjne (Stockwatch 8:00)")
    st.info("Moduł w przygotowaniu (Iteracja 2). Będzie gotowy po skonfigurowaniu integracji ze Stockwatch Premium.")
    
    st.subheader("Jak to będzie działać?")
    st.markdown("""
    1. **Scrapowanie:** Codziennie o 08:00 system pobierze aktualne wskaźniki (C/Z, C/WK, EV/EBITDA), omówienia wyników oraz wpisy z forów dla Twojej listy spółek ze **Stockwatch.pl**.
    2. **Analiza Fundamentalna:** GPW SME przeliczy punkty merytoryczne (Score 0-100) na bazie ustalonych reguł.
    3. **Rekomendacje:** Otrzymasz jasny wykaz: **KUPUJ / TRZYMAJ / SPRZEDAJ** wraz z uzasadnieniem przed otwarciem sesji giełdowej o 09:00.
    """)

with tab2:
    st.header("🎯 Realizacja Strategii Portfela")
    st.info("Moduł w przygotowaniu (Iteracja 3). Będzie nadzorować alokację i reguły ryzyka.")
    
    st.subheader("Planowane Funkcje Strategiczne:")
    st.markdown("""
    - **Limity Alokacji:** Maksymalnie 15% na jedną spółkę, 30% na sektor.
    - **Zarządzanie Ryzykiem:** Automatyczna kontrola progów Stop-Loss (-10%) i trailing Take-Profit (+25%).
    - **Rebalansowanie:** Sugestie zmian w portfelu na bazie oceny ryzyka generowanej przez Agenta QA & Risk Auditor.
    """)

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
                    df_history = pd.read_csv(HISTORY_PATH) if os.path.exists(HISTORY_PATH) else pd.DataFrame(columns=["Data", "Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)"])
                    df_history["Data"] = df_history["Data"].astype(str)
                    
                    new_row = {
                        "Data": rep_date,
                        "Wartość Całkowita (PLN)": parsed_data["total_value"] if parsed_data["total_value"] is not None else parsed_data["stocks_value"],
                        "Wycena Akcji (PLN)": parsed_data["stocks_value"],
                        "Gotówka (PLN)": parsed_data["cash_val"] if "cash_val" in parsed_data else parsed_data.get("cash_value", 0.0)
                    }
                    
                    if rep_date in df_history["Data"].values:
                        df_history.loc[df_history["Data"] == rep_date, ["Wartość Całkowita (PLN)", "Wycena Akcji (PLN)", "Gotówka (PLN)"]] = [
                            new_row["Wartość Całkowita (PLN)"], new_row["Wycena Akcji (PLN)"], new_row["Gotówka (PLN)"]
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
        
        # Calculate changes vs previous periods
        if len(df_history) >= 2:
            prev_row = df_history.iloc[-2]
            prev_val = prev_row["Wartość Całkowita (PLN)"]
            val_change_pct = ((latest_val - prev_val) / prev_val) * 100
            val_change_pln = latest_val - prev_val
            val_delta_str = f"{val_change_pln:+.2f} PLN ({val_change_pct:+.2f}%) vs poprzedni okres"
            val_delta_class = "delta-plus" if val_change_pln >= 0 else "delta-minus"
        else:
            val_delta_str = "Brak wcześniejszych danych"
            val_delta_class = ""
            
        # Calculate change vs base (Q1 2026 - first row)
        base_row = df_history.iloc[0]
        base_val = base_row["Wartość Całkowita (PLN)"]
        total_change_pct = ((latest_val - base_val) / base_val) * 100
        total_change_pln = latest_val - base_val
        total_delta_str = f"{total_change_pln:+.2f} PLN ({total_change_pct:+.2f}%) od startu (Q1 2026)"
        total_delta_class = "delta-plus" if total_change_pln >= 0 else "delta-minus"
        
        # Display KPIs using custom HTML for beautiful mobile-first design
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Wycena Portfela ({latest_date})</div>
                <div class="metric-value">{latest_val:,.2f} PLN</div>
                <div class="metric-delta {val_delta_class}">{val_delta_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Wynik od startu (Q1 2026)</div>
                <div class="metric-value">{total_change_pct:+.2f}%</div>
                <div class="metric-delta {total_delta_class}">{total_delta_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #28A745;">
                <div class="metric-title">Gotówka w Portfelu</div>
                <div class="metric-value">{latest_cash:,.2f} PLN</div>
                <div class="metric-delta" style="color: #6C757D;">Udział gotówki: {round((latest_cash/latest_val)*100, 2) if latest_val > 0 else 0}%</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Brak danych historycznych. Wgraj raport PDF lub wykaz instrumentów, aby wygenerować metryki.")

    st.markdown("---")

    # 3. WYKRES EWOLUCJI PORTFELA W CZASIE
    if not df_history.empty:
        st.subheader("Ewolucja Wartości Portfela")
        
        # Plotly chart
        fig = px.line(
            df_history, 
            x="Data", 
            y="Wartość Całkowita (PLN)",
            title="Wzrost Wartości Portfela (Erste BM)",
            markers=True,
            color_discrete_sequence=["#0066CC"]
        )
        fig.update_layout(
            hovermode="x unified", 
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_title="Data Raportu",
            yaxis_title="Wartość Całkowita (PLN)",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
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
            # To avoid clutter on mobile, only show names for holdings > 2.5% share
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
