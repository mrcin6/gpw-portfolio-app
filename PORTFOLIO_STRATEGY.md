# 🎯 PORTFOLIO_STRATEGY.md - Wizja i Strategia Inwestycyjna

## 1. Wizja Produktu (Product Vision)

Projekt **GPW Smart Assistant (StockMW)** ma na celu stworzenie zaawansowanego narzędzia wspierającego podejmowanie decyzji inwestycyjnych na Giełdzie Papierów Wartościowych w Warszawie (GPW). Aplikacja integruje analizę fundamentalną, kontrolę ryzyka portfela oraz śledzenie wyników organicznych w jednym responsywnym pulpicie nawigacyjnym.

Realizacja projektu dzieli się na dwa kluczowe cele strategiczne:

### Cel 1: ☀️ Rekomendacje Sesyjne 8:00 (Tab 1)
Zautomatyzowane dostarczanie rekomendacji inwestycyjnych (KUPUJ / TRZYMAJ / SPRZEDAJ) przed otwarciem każdej sesji giełdowej (do godziny 09:00).
- **Automatyzacja:** Cykliczny pobór najnowszych wskaźników fundamentalnych (C/Z, C/WK, EV/EBITDA, Stopa Dywidendy) dla spółek z listy obserwacyjnej (Watchlist).
- **Integracja:** Pobieranie danych bezpośrednio z portalu Stockwatch.pl (z obsługą autoryzacji sesyjnej za pomocą ciasteczka `PHPSESSID`) lub elastyczne przełączanie na źródła alternatywne (Yahoo Finance / Mock) w przypadku braku sesji.
- **Ocena Punktowa (Score 0-100):** Algorytmiczne wyliczanie syntetycznej oceny atrakcyjności spółki.

### Cel 2: 🎯 Realizacja i Kontrola Strategii (Tab 2)
Inteligentne zarządzanie ryzykiem i składem portfela w oparciu o aktualny stan posiadania wczytywany z raportów PDF Erste BM.
- **Kontrola Limitów Alokacji:** Automatyczne weryfikowanie udziału pojedynczych spółek (maksymalnie 15%) oraz całych sektorów (maksymalnie 30%) w celu zapobiegania nadmiernej koncentracji kapitału.
- **Monitoring Pozycji (Stop-Loss / Take-Profit):** Śledzenie bieżących kursów aktywów z portfela za pomocą Yahoo Finance i natychmiastowe alarmowanie o naruszeniu progów cięcia strat (Stop-Loss -10%) lub realizacji zysków (trailing Take-Profit +25%).
- **Wizualizacja Sektorowa:** Interaktywne wykresy alokacji ułatwiające rebalansowanie portfela.

---

## 2. Ustawienia Ryzyka (Risk Settings)
Parametry ryzyka są importowane bezpośrednio z pliku konfiguracyjnego `config/strategy.json` i podlegają stałemu audytowi:

| Parametr Ryzyka | Wartość | Opis |
| :--- | :---: | :--- |
| **Maksymalna alokacja na spółkę** | `15.0%` | Maksymalny dozwolony udział pojedynczego waloru w całkowitej wycenie portfela akcyjnego. |
| **Maksymalna alokacja na sektor** | `30.0%` | Maksymalna skumulowana wycena spółek z danego sektora gospodarki. |
| **Próg cięcia strat (Stop-Loss)** | `-10.0%` | Próg procentowy straty od ceny zakupu, po którym system sugeruje natychmiastową sprzedaż. |
| **Kroczący realizator zysku (Trailing Take-Profit)** | `+25.0%` | Próg aktywacji trailing stopu, zabezpieczający wypracowane zyski przy zmianach trendu. |
| **Próg zakupu (Scoring BUY)** | `>= 70` | Minimalna ocena wskaźnikowa kwalifikująca spółkę do rekomendacji KUPUJ. |
| **Próg sprzedaży (Scoring SELL)** | `<= 30` | Ocena wskaźnikowa kwalifikująca spółkę do natychmiastowej rekomendacji SPRZEDAJ. |

---

## 3. Lista Obserwacyjna (Watchlist)
System monitoruje na bieżąco zestaw 11 wyselekcjonowanych walorów z rynku głównego GPW i NewConnect, zdefiniowanych w `config/watchlist.json`:

1. **KRUK** (Wierzytelności / Finanse)
2. **LPP** (Handel detaliczny / Odzież)
3. **GRODNO** (Dystrybucja materiałów elektrotechnicznych)
4. **RYVU** (Biotechnologia / Badania kliniczne)
5. **SYNEKTIK** (Technologie medyczne / Urządzenia robotyczne)
6. **MODIVO** (E-commerce / Odzież i obuwie)
7. **NEWAG** (Przemysł taboru szynowego)
8. **GPW** (Rynki finansowe / Infrastruktura giełdowa)
9. **SEKO** (Przetwórstwo spożywcze / Rybne)
10. **DOMDEV** (Budownictwo mieszkaniowe / Deweloper)
11. **XTB** (Usługi finansowe / Dom maklerski)
