#!/bin/bash

# ==============================================================================
# GPW Smart Assistant (StockMW) - Wieloagentowy Rurociąg Deweloperski (Loop Pipeline)
# ==============================================================================

MAX_ITER=5
ITER=1
SCORE_QA=1

echo "=== START WIELOAGENTOWEJ PĘTLI DEWELOPERSKO-AUDYTOWEJ ==="

while [ $SCORE_QA -lt 4 ] && [ $ITER -le $MAX_ITER ]; do
  echo "=========================================="
  echo " ITERACJA $ITER z $MAX_ITER"
  echo "=========================================="

  # 1. STRATEGY PO AGENT
  echo "[1/6] PO definiuje strategię..."
  gemini --prompt "$(cat .gemini/prompts/strategy_po_prompt.md)

Zaktualizuj PORTFOLIO_STRATEGY.md na podstawie config/ i EVAL.md" > PORTFOLIO_STRATEGY.md

  # 2. DATA RESEARCHER
  echo "[2/6] Data Researcher ustala zaktualizowane źródła danych..."
  gemini --prompt "$(cat .gemini/prompts/tech_researcher_prompt.md)

Opracuj integracje w DATA_SOURCES.md na podstawie PORTFOLIO_STRATEGY.md i EVAL.md" > DATA_SOURCES.md

  # 3. FINANCIAL SME
  echo "[3/6] Financial SME tworzy wzory i algorytmy..."
  gemini --prompt "$(cat .gemini/prompts/financial_expert_prompt.md)

Opracuj algorytmy w ANALYSIS_RULES.md na podstawie DATA_SOURCES.md i EVAL.md" > ANALYSIS_RULES.md

  # 4. QUANT & CODER AGENT (DEVELOPER)
  echo "[4/6] Quant & Coder wdraża/poprawia kod..."
  gemini --prompt "$(cat .gemini/prompts/coder_prompt.md)

Zbuduj lub popraw kod w src/ i app.py zgodnie z ANALYSIS_RULES.md i sekcją DELTA w EVAL.md"

  # 5. UX & DASHBOARD AGENT
  echo "[5/6] UX Agent weryfikuje prezentację danych..."
  gemini --prompt "$(cat .gemini/prompts/ux_prompt.md)

Przeanalizuj interfejs/raport pod kątem czytelności i UX." > UX_AUDIT.md

  # 6. QA & RISK AUDITOR
  echo "[6/6] QA Audytor weryfikuje kod i ryzyko..."
  gemini --prompt "$(cat .gemini/prompts/qa_prompt.md)

Przeprowadź audyt kodu i ryzyka. Zapisz SCORE (1-5) i STATUS w EVAL.md" > EVAL.md

  # Pobranie oceny z EVAL.md (np. SCORE: 4)
  SCORE_QA=$(grep -E '^SCORE:[[:space:]]*[1-5]' EVAL.md | tr -cd '1-5' || echo "1")
  echo "--> Ocena QA w iteracji $ITER: $SCORE_QA / 5"

  if [ "$SCORE_QA" -ge 4 ]; then
    echo " [SUCCESS] Projekt spełnia wymagania jakościowe (Score $SCORE_QA >= 4) w iteracji $ITER!"
    break
  else
    echo " [REJECTED] Wymagane poprawki (Score $SCORE_QA < 4). Przechodzę do kolejnej pętli..."
    ((ITER++))
  fi
done

if [ "$SCORE_QA" -lt 4 ]; then
  echo " [WARNING] Osiągnięto limit iteracji ($MAX_ITER) bez uzyskania wyniku jakościowego >= 4."
fi
