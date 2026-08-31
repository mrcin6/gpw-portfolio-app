"""
Jednorazowy skrypt migracyjny: przenosi dane z data/ do data/erste/
Uruchom raz: python src/migrate_to_multiportfolio.py
"""
import os
import shutil
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_DATA = os.path.join(BASE_DIR, "data")

FILES_TO_MIGRATE = [
    "current_holdings.csv",
    "portfolio_history.csv",
    "entry_prices.json",
    "deposit_history.json",
    "stockwatch_alerts.json",
]

PORTFOLIO_DIRS = ["erste", "ing", "ikze"]

EMPTY_HOLDINGS = "Spółka,Ilość,Kurs (PLN),Wycena (PLN),Udział (%)\n"
EMPTY_HISTORY  = "Data,Wartość Całkowita (PLN),Wycena Akcji (PLN),Gotówka (PLN),Wpłaty Skumulowane (PLN),Zysk (PLN)\n"

def migrate():
    # Create subdirectories
    for p in PORTFOLIO_DIRS:
        os.makedirs(os.path.join(OLD_DATA, p), exist_ok=True)
        print(f"Created: data/{p}/")

    # Move Erste files
    erste_dir = os.path.join(OLD_DATA, "erste")
    for fname in FILES_TO_MIGRATE:
        src = os.path.join(OLD_DATA, fname)
        dst = os.path.join(erste_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.move(src, dst)
            print(f"Moved: data/{fname} → data/erste/{fname}")
        elif os.path.exists(dst):
            print(f"Already migrated: data/erste/{fname}")

    # Create empty settings for each portfolio
    for p in PORTFOLIO_DIRS:
        settings_path = os.path.join(OLD_DATA, p, "portfolio_settings.json")
        if not os.path.exists(settings_path):
            default = {"total_deposits": 0.0, "phpsessid": "", "strategy": p}
            with open(settings_path, "w") as f:
                json.dump(default, f, indent=2)
            print(f"Created: data/{p}/portfolio_settings.json")

    # Create empty data files for ING and IKE/IKZE
    for p in ["ing", "ikze"]:
        pdir = os.path.join(OLD_DATA, p)
        holdings_path = os.path.join(pdir, "current_holdings.csv")
        history_path  = os.path.join(pdir, "portfolio_history.csv")
        entry_path    = os.path.join(pdir, "entry_prices.json")
        deposits_path = os.path.join(pdir, "deposit_history.json")
        alerts_path   = os.path.join(pdir, "stockwatch_alerts.json")

        if not os.path.exists(holdings_path):
            with open(holdings_path, "w") as f: f.write(EMPTY_HOLDINGS)
        if not os.path.exists(history_path):
            with open(history_path, "w") as f: f.write(EMPTY_HISTORY)
        if not os.path.exists(entry_path):
            with open(entry_path, "w") as f: json.dump({}, f)
        if not os.path.exists(deposits_path):
            with open(deposits_path, "w") as f: json.dump([], f)
        if not os.path.exists(alerts_path):
            with open(alerts_path, "w") as f: json.dump({"seen_ids": [], "articles": []}, f)
        print(f"Initialized empty files for: data/{p}/")

    print("\nMigracja zakończona. Sprawdź data/erste/, data/ing/, data/ikze/")

if __name__ == "__main__":
    migrate()
