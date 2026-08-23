# 📈 GPW Smart Assistant - Portfolio Dashboard (MVP)

Autonomiczny asystent inwestycyjny na Giełdzie Papierów Wartościowych w Warszawie (GPW). Wersja MVP skupia się na **Celu 3 (Podsumowanie i Wyniki Portfela)** z pełną obsługą parsowania wyciągów kwartalnych oraz wykazów instrumentów PDF z Erste Biuro Maklerskie.

## 🚀 Szybki Start

### 1. Wymagania
Upewnij się, że masz zainstalowanego Pythona (zalecany Python 3.9 lub nowszy).

### 2. Instalacja zależności
Przejdź do katalogu projektu i zainstaluj potrzebne pakiety:
```bash
cd gpw-portfolio-app
pip install -r requirements.txt
```

### 3. Uruchomienie aplikacji
Uruchom serwer Streamlit lokalnie:
```bash
streamlit run app.py
```
Aplikacja otworzy się automatycznie w Twojej przeglądarce pod adresem: `http://localhost:8501`.

## 📊 Funkcjonalności MVP (Cel 3)
- **Automatyczny Import PDF:** Możesz wgrywać wyciągi kwartalne ("Kwartalne zestawienie aktywów") oraz wykazy instrumentów ("Instrumenty finansowe raport") wygenerowane z Erste Biuro Maklerskie.
- **Dynamiczna Aktualizacja:** Po wgraniu nowego pliku PDF system automatycznie wyodrębnia datę, wartość gotówki, wycenę akcji i pełen wykaz pozycji, po czym zapisuje je w lokalnej bazie CSV (`data/`).
- **Interaktywne Wykresy:** Wizualizacja ewolucji wartości całkowitej portfela w czasie na wykresie liniowym Plotly.
- **Struktura Aktywów:** Wykres kołowy oraz szczegółowa tabela przedstawiająca aktualne udziały poszczególnych spółek w portfelu.
- **Placeholdery dla Celu 1 & 2:** Zakładki z projektami integracji ze Stockwatch Premium oraz automatycznej kontroli strategii portfela (limity alokacji, Stop-Loss).

## 📂 Struktura Projektu
- `app.py` — Główny kod interfejsu Streamlit.
- `src/pdf_parser.py` — Logika parsowania plików PDF z Erste BM z użyciem `pdfplumber` i wyrażeń regularnych.
- `data/portfolio_history.csv` — Historia wycen portfela (baza danych).
- `data/current_holdings.csv` — Aktualny skład i struktura portfela.
- `requirements.txt` — Wykaz bibliotek Pythona.
