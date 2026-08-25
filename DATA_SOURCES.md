# 📊 DATA_SOURCES.md - Źródła Danych i Integracje API

## 1. Stockwatch.pl (Analiza Fundamentalna)

Portal **Stockwatch.pl** jest głównym źródłem wskaźników fundamentalnych dla polskich spółek giełdowych.

### Mechanizm Scrapowania i Autoryzacji
- **URL Bazowy:** `https://www.stockwatch.pl/gpw/{slug}.aspx`
- **Metoda:** HTTP GET przy użyciu biblioteki `requests` i parsera HTML `BeautifulSoup4`.
- **Autoryzacja (Premium):** Dostęp do pełnych i nieopóźnionych wskaźników finansowych na Stockwatch.pl wymaga zalogowania. Sesja jest autoryzowana za pomocą ciasteczka sesyjnego o nazwie `PHPSESSID`.
- **Nagłówek Cookies:** W każdym żądaniu do Stockwatch wysyłany jest nagłówek:
  ```http
  Cookie: PHPSESSID={wartość_ciasteczka}
  ```
- **Identyfikacja tagów w kodzie HTML:**
  - Wskaźnik **C/Z** (Cena / Zysk): Szukany w tabelach wskaźników wewnątrz tagów HTML zawierających tekst `"C/Z"`.
  - Wskaźnik **C/WK** (Cena / Wartość Księgowa): Szukany w tagach zawierających `"C/WK"`.
  - Wskaźnik **EV/EBITDA**: Szukany w tagach zawierających `"EV/EBITDA"`.
  - **Stopa Dywidendy**: Szukany w tagach zawierających `"Stopa dywidendy"` lub `"Dywidenda"`.

### Strategie Fallback (Obsługa Błędów i Braków)
Aby zapewnić 100% stabilności aplikacji (odporność na brak sieci, wygaśnięcie ciasteczka lub zablokowanie IP), wdrożono 3-poziomową architekturę pobierania wskaźników:

1. **Poziom 1: Stockwatch Premium** (jeśli podano ważny `PHPSESSID` i pobieranie się powiodło).
2. **Poziom 2: Yahoo Finance API** (jeśli pobieranie ze Stockwatch zawiedzie). Pobiera wskaźniki z `yfinance` przy użyciu pól:
   - `trailingPE` / `forwardPE` dla C/Z.
   - `priceToBook` dla C/WK.
   - `enterpriseToEbitda` dla EV/EBITDA.
   - `dividendYield` dla Stopy Dywidendy.
3. **Poziom 3: Lokalne Dane Stabilne (Mock/Default)** (jeśli poziom 1 i 2 zawiodą, np. brak internetu). Zwraca predefiniowane, realistyczne wskaźniki dla każdej spółki z niewielką losowością sesyjną (szumem), aby interfejs pozostawał interaktywny i dynamiczny.

---

## 2. Yahoo Finance (Ceny Real-Time i Metryki Rynkowe)

Platforma **Yahoo Finance** jest darmowym i stabilnym źródłem cen rynkowych opóźnionych o max 15 minut.

### Integracja Techniczna
- **Biblioteka:** `yfinance` (Python wrapper).
- **Format Tickerów GPW:** Tickers na GPW wymagają przyrostka `.WA` (Warsaw), np.:
  - `KRUK` -> `KRU.WA`
  - `LPP` -> `LPP.WA`
  - `XTB` -> `XTB.WA`
- **Funkcjonalność:**
  - Pobieranie najnowszych kursów zamknięcia (`regularMarketPrice` lub `currentPrice`) dla pozycji w portfelu.
  - Wyciąganie sektorów gospodarczych (`sector`) w celu kontroli limitów dywersyfikacji.
  - Pobieranie wskaźników fundamentalnych jako fallback dla Stockwatcha.

---

## 3. Schematy i Struktury Danych (Data Schemas)

### A. Schemat Wskaźników Fundamentalnych Spółki
```json
{
  "ticker": "KRUK",
  "c_z": 9.45,
  "c_wk": 1.62,
  "ev_ebitda": 7.80,
  "dywidenda_pct": 5.20,
  "price": 435.70,
  "source": "Stockwatch / Yahoo / Fallback",
  "status": "Success / Fallback"
}
```

### B. Schemat Pozycji Portfelowej (Holding Status)
```json
{
  "ticker": "KRUK",
  "quantity": 109,
  "purchase_price": 435.70,
  "current_price": 442.10,
  "valuation": 48188.90,
  "share_pct": 35.79,
  "sector": "Finanse / Windykacja",
  "gain_loss_pct": 1.47,
  "stop_loss_triggered": false,
  "take_profit_triggered": false
}
```
