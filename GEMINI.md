# Project Instructions - GPW Smart Assistant (StockMW)

## 📌 Standard deweloperski i operacyjny

### 1. Rejestr Statusu Po Wdrożeniach (Deploy Workflow Mandate)
Każdorazowo po pomyślnym wdrożeniu (deploy) aplikacji lub zakończeniu istotnego etapu prac, asystent **ma absolutny obowiązek** zaktualizować status projektu i pozostawić szczegółowy, czytelny rejestr stanu w folderze na Biurku użytkownika:
- **Ścieżka rejestru:** `/Users/marcinwcislo/Desktop/GPW_Portfolio_Assistant_Status/PROJECT_STATUS.md`

Ten plik służy jako nadrzędny dokument wejściowy (Context Index) dla kolejnej sesji asystenckiej, umożliwiając natychmiastowe podjęcie prac bez utraty kontekstu.

### 2. Standardy Architektoniczne
- **Stylizowanie UI:** Streamlit Vanilla CSS (poprzez `st.markdown(..., unsafe_allow_html=True)`) z zachowaniem spójnej gamy kolorystycznej i responsywności pod urządzenia mobilne.
- **Konfiguracja Środowiska:** Wszelkie zależności muszą być utrzymywane w lokalnym wirtualnym środowisku `/Users/marcinwcislo/gpw-portfolio-app/venv` i dokumentowane w `requirements.txt`.
- **Parser PDF (`src/pdf_parser.py`):** Wszelkie modyfikacje parsera muszą utrzymywać zarówno dedykowane fallbacki dla pre-populowanych historycznych plików PDF (Q1, Q2, Q3 2026), jak i generyczny parser wyrażeń regularnych dla nowych plików.
