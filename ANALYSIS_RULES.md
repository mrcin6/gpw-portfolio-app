# 📐 ANALYSIS_RULES.md - Algorytmy Merytoryczne i Reguły Inwestycyjne

## 1. Wieloczynnikowy Model Punktowy (0-100 Score)

Syntetyczna ocena atrakcyjności spółki (Score) wyliczana jest jako ważona średnia pięciu składowych fundamentalnych i technicznych:

$$Score = 0.30 \cdot S_{C/Z} + 0.20 \cdot S_{C/WK} + 0.20 \cdot S_{EV/EBITDA} + 0.10 \cdot S_{DY} + 0.20 \cdot S_{Trend}$$

### A. Ocena C/Z (Cena / Zysk) - Waga: 30%
Służy do oceny zyskowności spółki i wyceny rynkowej jej zysków.

| Zakres C/Z | Ocena ($S_{C/Z}$) | Klasyfikacja |
| :--- | :---: | :--- |
| $C/Z < 0$ | **0** | Strata netto (wysokie ryzyko) |
| $0 \le C/Z < 5$ | **50** | Niedowartościowanie lub "pułapka wartości" |
| $5 \le C/Z \le 12$ | **100** | **Optymalna wycena (Excellent)** |
| $12 < C/Z \le 20$ | **70** | Godziwa wycena (Fair Value) |
| $20 < C/Z \le 35$ | **40** | Przewartościowanie |
| $C/Z > 35$ | **10** | Balon spekulacyjny / skrajne przewartościowanie |

### B. Ocena C/WK (Cena / Wartość Księgowa) - Waga: 20%
Mierzy wycenę majątku spółki przez rynek.

| Zakres C/WK | Ocena ($S_{C/WK}$) | Klasyfikacja |
| :--- | :---: | :--- |
| $C/WK < 0$ | **0** | Ujemny kapitał własny (zagrożenie upadłością) |
| $0 \le C/WK \le 1.0$ | **100** | **Głębokie niedowartościowanie (Graham Style)** |
| $1.0 < C/WK \le 2.5$ | **80** | Zdrowa wycena wzrostowa (Optimal) |
| $2.5 < C/WK \le 4.0$ | **50** | Wysoka premia rynkowa |
| $C/WK > 4.0$ | **20** | Droga spółka (wysokie ryzyko korekty) |

### C. Ocena EV/EBITDA - Waga: 20%
Wskaźnik wyceny operacyjnej przedsiębiorstwa, uwzględniający zadłużenie.

| Zakres EV/EBITDA | Ocena ($S_{EV/EBITDA}$) | Klasyfikacja |
| :--- | :---: | :--- |
| $EV/EBITDA < 0$ | **0** | Ujemny wynik operacyjny EBITDA |
| $0 \le EV/EBITDA \le 6.0$ | **100** | **Wyjątkowo tania operacyjnie spółka** |
| $6.0 < EV/EBITDA \le 11.0$ | **75** | Średnia rynkowa (godziwa wycena) |
| $11.0 < EV/EBITDA \le 16.0$ | **40** | Droga wycena operacyjna |
| $EV/EBITDA > 16.0$ | **15** | Skrajnie wysoka wycena |

### D. Ocena Stopy Dywidendy (DY) - Waga: 10%
Premiuje spółki dzielące się zyskiem z akcjonariuszami.

| Stopa Dywidendy (%) | Ocena ($S_{DY}$) | Klasyfikacja |
| :--- | :---: | :--- |
| $DY = 0\%$ | **0** | Spółka wzrostowa lub w kłopotach (brak dywidendy) |
| $0\% < DY < 2\%$ | **30** | Symboliczna dywidenda |
| $2\% \le DY < 5\%$ | **70** | Przyzwoity podział zysku |
| $5\% \le DY \le 10\%$ | **100** | **Optymalna stopa dywidendy (Cash Cow)** |
| $DY > 10\%$ | **80** | Ekstremalnie wysoka dywidenda (możliwa pułapka) |

### E. Ocena Trendu Technicznego - Waga: 20%
Weryfikuje, czy spółka znajduje się w trendzie wzrostowym (podąża z rynkiem).

- **Warunek:** Porównanie bieżącego kursu zamknięcia ($P_{now}$) z 50-dniową Prostą Średnią Kroczącą ($SMA_{50}$).
- **Reguła:**
  - Jeśli $P_{now} > SMA_{50} \implies S_{Trend} = 100$ (Silny trend wzrostowy / Sygnał momentum).
  - Jeśli $P_{now} \le SMA_{50} \implies S_{Trend} = 30$ (Trend spadkowy lub konsolidacja).
  - *Uwaga:* W przypadku braku danych historycznych dla SMA, stosuje się fallback: 30-dniowa stopa zwrotu $> 0 \implies 100$, w przeciwnym razie $30$.

---

## 2. Matryca Rekomendacji (Recommendation Matrix)

Syntetyczny wynik punktowy przekłada się bezpośrednio na decyzję inwestycyjną:

| Wynik Końcowy (Score) | Rekomendacja | Kolor Badge | Akcja |
| :---: | :---: | :---: | :--- |
| **Score $\ge 70$** | **KUPUJ** (BUY) | **Zieleń** (`#28A745`) | Spółka silna fundamentalnie w trendzie wzrostowym. |
| **$30 < Score < 70$** | **TRZYMAJ** (HOLD) | **Szary/Żółty** (`#FFC107`) | Neutralna wycena. Utrzymaj obecną pozycję, nie dokupuj. |
| **Score $\le 30$** | **SPRZEDAJ** (SELL) | **Czerwień** (`#DC3545`) | Pogorszenie fundamentów lub przewartościowanie. |

---

## 3. Reguły Ryzyka i Alerty Portfelowe (Risk Rules)

Kontrola ryzyka działa w oparciu o sztywne wytyczne z `config/strategy.json`:

### A. Limit Alokacji Pojedynczego Waloru (Maks. 15%)
Udział danej spółki w całkowitej wartości akcji portfela nie powinien przekraczać 15%:

$$Udział_{Spółka} = \frac{Wycena_{Spółka}}{Wartość\ Portfela\ Akcji} \cdot 100\%$$

- **Naruszenie limitu ($Udział > 15\%$):** Wyświetlenie ostrzeżenia (Warning) z sugerowaną redukcją pozycji o wartość nadwyżki.

### B. Limit Alokacji Sektorowej (Maks. 30%)
Suma udziałów wszystkich spółek z danego sektora gospodarki nie może przekraczać 30%:

$$Udział_{Sektor} = \sum_{i \in Sektor} Udział_{Spółka, i} \cdot 100\%$$

- **Naruszenie limitu ($Udział_{Sektor} > 30\%$):** Wyświetlenie krytycznego ostrzeżenia (Critical Warning) sugerującego rebalansowanie całego sektora.

### C. Zabezpieczenie Stop-Loss (-10%)
Automatyczne monitorowanie straty na posiadanych pozycjach:

$$Zysk/Strata = \frac{Kurs_{Bieżący} - Kurs_{Zakupu}}{Kurs_{Zakupu}} \cdot 100\%$$

- **Warunek aktywacji:** Jeśli $Zysk/Strata \le -10.0\%$, generowany jest krytyczny alert **"STOP-LOSS TRIGGERED!"** sugerujący natychmiastowe zamknięcie pozycji w celu ochrony kapitału.

### D. Zabezpieczenie Take-Profit (+25% Trailing)
Zabezpieczenie zysków po osiągnięciu znaczącego wzrostu:

- **Warunek aktywacji:** Jeśli maksymalny wypracowany zysk od momentu zakupu osiągnął $\ge 25.0\%$, system uruchamia wskaźnik **Take-Profit Active**.
- **Wskazówka operacyjna:** System informuje o konieczności podciągnięcia zlecenia Stop-Loss w tryb kroczący (trailing) lub zabezpieczenia wypracowanego zysku.
