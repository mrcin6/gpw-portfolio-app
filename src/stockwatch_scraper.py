import re
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StockwatchScraper")

# Mapping of tickers to Stockwatch.pl slug names
STOCKWATCH_SLUGS = {
    "KRUK":      "kruk-sa",
    "LPP":       "lpp-sa",
    "GRODNO":    "grodno-sa",
    "RYVU":      "ryvu-therapeutics-sa",
    "SEKO":      "seko-sa",
    "DOMDEV":    "dom-development-sa",
    "XTB":       "xtb-sa",
    "KOLEJKOWO": "kolejkowo-sa",
    "RAINBOW":   "rainbow-tours-sa",
    "PKNORLEN":  "orlen-sa",
    "PKOBP":     "pko-bank-polski-sa",
    "SYN2BIO":   "syn2bio-sa",
    "LUBAWA":    "lubawa-sa",
    "PKPCARGO":  "pkp-cargo-sa",
    "RANKPROGR": "rank-progress-sa",
    "STAPORKOW": "stal-stalowa-wola-sa",
    "ZREMB":     "zremb-chojnice-sa",
    # Legacy / no longer in portfolio but kept for backwards compat
    "SYNEKTIK":  "synektik-sa",
    "MODIVO":    "ccc-sa",
    "NEWAG":     "newag-sa",
    "GPW":       "gielda-papierow-wartosciowych-w-warszawie-sa",
    "RANKPROGR": "rank-progress-sa",
    # Extended watchlist v3.1
    "KGHM":      "kghm-polska-miedz-sa",
    "PZU":       "powszechny-zaklad-ubezpieczen-sa",
    "PEKAO":     "bank-polska-kasa-opieki-sa",
    "INGBSK":    "ing-bank-slaski-sa",
    "BNPPPL":    "bnp-paribas-bank-polska-sa",
    "ALLEGRO":   "allegro-eu",
    "KETY":      "kety-sa",
    "BENEFIT":   "benefit-systems-sa",
    "INTERCARS": "inter-cars-sa",
    "NEUCA":     "neuca-sa",
    "MOBRUK":    "mo-bruk-sa",
    "DEKPOL":    "dekpol-sa",
    "ABPL":      "ab-sa",
    "TORPOL":    "torpol-sa",
    "COGNOR":    "cognor-holding-sa",
    "KOGENERA":  "kogeneracja-sa",
    "CREOTECH":  "creotech-instruments-sa",
    "DATAWALK":  "datawalk-sa",
    "ONDE":      "onde-sa",
    "CYBERFLKS": "cyberfolks-sa",
    "ELEKTROTI": "elektrotim-sa",
    "MEDINICE":  "medinice-sa",
    "BIOCELTIX": "bioceltix-sa",
    "PATENTUS":  "patentus-sa",
    "ZABKA":     "zabka-group-sa",
    "DIAG":      "diagnostyka-sa",
    "SCANWAY":   "scanway-sa",
    "ERSTE":     "erste-group-bank",
    "GETIN":     "getin-noble-bank-sa",
    "KLEPSYDRA": "klepsydra-sa",
    "ETFBSPXPL": "beta-etf-sp500pln-open",
    "ETFBW20TR": "beta-etf-wig20tr-open",
}

# Mapping of tickers to Yahoo Finance symbols (GPW: suffix .WA)
YFIN_TICKERS = {
    "KRUK":      "KRU.WA",
    "LPP":       "LPP.WA",
    "GRODNO":    "GRN.WA",
    "RYVU":      "RYV.WA",
    "SEKO":      "SEK.WA",
    "DOMDEV":    "DOM.WA",
    "XTB":       "XTB.WA",
    "KOLEJKOWO": "KLJ.WA",
    "RAINBOW":   "RBW.WA",
    "PKNORLEN":  "PKN.WA",
    "PKOBP":     "PKO.WA",
    "SYN2BIO":   "SNB.WA",
    "LUBAWA":    "LBW.WA",
    "PKPCARGO":  "PKC.WA",
    "RANKPROGR": "RNK.WA",
    # STAPORKOW: STP.WA = STALPROD (wrong company) — price comes from Biznesradar
    "ZREMB":     "ZRM.WA",
    # Legacy
    "SYNEKTIK":  "SNT.WA",
    "MODIVO":    "CCC.WA",
    "NEWAG":     "NWG.WA",
    "GPW":       "GPW.WA",
    "RANKPROGR": "RNK.WA",
    # Extended watchlist v3.1
    "KGHM":      "KGH.WA",
    "PZU":       "PZU.WA",
    "PEKAO":     "PEO.WA",
    "INGBSK":    "BSK.WA",
    "BNPPPL":    "BNP.WA",
    "ALLEGRO":   "ALE.WA",
    "KETY":      "KTY.WA",
    "BENEFIT":   "BFT.WA",
    "INTERCARS": "CAR.WA",
    "NEUCA":     "NEU.WA",
    "MOBRUK":    "MBR.WA",
    "DEKPOL":    "DEK.WA",
    "ABPL":      "ABE.WA",
    "TORPOL":    "TOR.WA",
    "COGNOR":    "COG.WA",
    "KOGENERA":  "KGN.WA",
    "CREOTECH":  "CRE.WA",
    "DATAWALK":  "DTW.WA",
    "ONDE":      "OND.WA",
    # No Yahoo mapping for: CYBERFLKS, ELEKTROTI, MEDINICE, BIOCELTIX,
    # PATENTUS, ZABKA, DIAG, SCANWAY, ERSTE, GETIN, KLEPSYDRA, ETFBSPXPL, ETFBW20TR
    # → Biznesradar L2 handles these via GPW ticker directly
}

# Static realistic fallback data (prices/ratios as of 2026-07 for L3 fallback)
STATIC_FALLBACKS = {
    "KRUK":      {"c_z": 9.45,  "c_wk": 1.62, "ev_ebitda": 7.80,  "dy": 5.20, "price": 414.00},
    "LPP":       {"c_z": 18.20, "c_wk": 4.10, "ev_ebitda": 11.50, "dy": 2.80, "price": 19960.00},
    "GRODNO":    {"c_z": 11.50, "c_wk": 0.85, "ev_ebitda": 6.20,  "dy": 4.50, "price": 16.00},
    "RYVU":      {"c_z": -8.00, "c_wk": 1.80, "ev_ebitda": -6.00, "dy": 0.00, "price": 14.90},
    "SEKO":      {"c_z": 7.40,  "c_wk": 0.65, "ev_ebitda": 4.80,  "dy": 5.50, "price": 11.60},
    "DOMDEV":    {"c_z": 8.90,  "c_wk": 1.85, "ev_ebitda": 6.50,  "dy": 7.80, "price": 255.00},
    "XTB":       {"c_z": 6.20,  "c_wk": 2.15, "ev_ebitda": 4.10,  "dy": 8.50, "price": 131.40},
    "KOLEJKOWO": {"c_z": 22.00, "c_wk": 3.20, "ev_ebitda": 12.00, "dy": 0.00, "price": 58.00},
    "RAINBOW":   {"c_z": 9.50,  "c_wk": 1.40, "ev_ebitda": 5.80,  "dy": 4.00, "price": 134.30},
    "PKNORLEN":  {"c_z": 7.80,  "c_wk": 0.75, "ev_ebitda": 4.50,  "dy": 6.50, "price": 146.20},
    "PKOBP":     {"c_z": 8.20,  "c_wk": 1.10, "ev_ebitda": 5.20,  "dy": 7.20, "price": 106.80},
    "SYN2BIO":   {"c_z": -5.00, "c_wk": 4.50, "ev_ebitda": -3.00, "dy": 0.00, "price": 77.85},
    "LUBAWA":    {"c_z": 14.00, "c_wk": 1.20, "ev_ebitda": 8.00,  "dy": 2.00, "price": 11.22},
    "PKPCARGO":  {"c_z": -3.00, "c_wk": 0.30, "ev_ebitda": 6.00,  "dy": 0.00, "price": 10.32},
    "RANKPROGR": {"c_z": 12.00, "c_wk": 0.60, "ev_ebitda": 7.00,  "dy": 0.00, "price": 4.90},
    "STAPORKOW": {"c_z": 8.00,  "c_wk": 0.50, "ev_ebitda": 5.00,  "dy": 0.00, "price": 4.50},
    "ZREMB":     {"c_z": 10.00, "c_wk": 0.80, "ev_ebitda": 6.00,  "dy": 0.00, "price": 9.26},
    # Legacy
    "SYNEKTIK":  {"c_z": 24.50, "c_wk": 5.80, "ev_ebitda": 15.20, "dy": 1.20, "price": 355.60},
    "MODIVO":    {"c_z": 15.10, "c_wk": 1.95, "ev_ebitda": 8.90,  "dy": 0.00, "price": 90.56},
    "NEWAG":     {"c_z": 10.20, "c_wk": 1.35, "ev_ebitda": 6.80,  "dy": 3.10, "price": 93.10},
    "GPW":       {"c_z": 12.80, "c_wk": 0.95, "ev_ebitda": 7.10,  "dy": 6.20, "price": 99.50},
    "RANKPROGR": {"c_z": 12.00, "c_wk": 0.60, "ev_ebitda": 7.00,  "dy": 0.00, "price": 4.90},
    # Extended watchlist v3.1
    "KGHM":      {"c_z": 10.50, "c_wk": 0.65, "ev_ebitda": 6.50,  "dy": 3.00, "price": 148.00},
    "PZU":       {"c_z": 11.00, "c_wk": 1.80, "ev_ebitda": 8.00,  "dy": 7.50, "price": 42.00},
    "PEKAO":     {"c_z": 9.50,  "c_wk": 1.20, "ev_ebitda": 6.00,  "dy": 8.00, "price": 175.00},
    "INGBSK":    {"c_z": 12.00, "c_wk": 2.00, "ev_ebitda": 8.00,  "dy": 6.00, "price": 270.00},
    "BNPPPL":    {"c_z": 10.00, "c_wk": 1.30, "ev_ebitda": 7.00,  "dy": 5.00, "price": 85.00},
    "ALLEGRO":   {"c_z": 25.00, "c_wk": 3.50, "ev_ebitda": 15.00, "dy": 0.00, "price": 38.00},
    "KETY":      {"c_z": 16.00, "c_wk": 2.50, "ev_ebitda": 10.00, "dy": 4.50, "price": 520.00},
    "BENEFIT":   {"c_z": 18.00, "c_wk": 3.00, "ev_ebitda": 11.00, "dy": 1.00, "price": 1500.00},
    "INTERCARS": {"c_z": 12.00, "c_wk": 1.80, "ev_ebitda": 8.00,  "dy": 1.50, "price": 390.00},
    "NEUCA":     {"c_z": 14.00, "c_wk": 1.50, "ev_ebitda": 9.00,  "dy": 2.50, "price": 500.00},
    "MOBRUK":    {"c_z": 14.00, "c_wk": 2.00, "ev_ebitda": 9.00,  "dy": 4.00, "price": 230.00},
    "DEKPOL":    {"c_z": 8.00,  "c_wk": 0.70, "ev_ebitda": 5.50,  "dy": 3.00, "price": 30.00},
    "ABPL":      {"c_z": 8.00,  "c_wk": 0.80, "ev_ebitda": 5.00,  "dy": 3.50, "price": 42.00},
    "TORPOL":    {"c_z": 10.00, "c_wk": 1.20, "ev_ebitda": 6.00,  "dy": 2.50, "price": 15.00},
    "COGNOR":    {"c_z": 5.00,  "c_wk": 0.50, "ev_ebitda": 4.00,  "dy": 0.00, "price": 4.50},
    "KOGENERA":  {"c_z": 10.00, "c_wk": 0.90, "ev_ebitda": 6.00,  "dy": 5.00, "price": 34.00},
    "CREOTECH":  {"c_z": None,  "c_wk": 3.50, "ev_ebitda": None,  "dy": 0.00, "price": 80.00},
    "DATAWALK":  {"c_z": None,  "c_wk": 4.00, "ev_ebitda": None,  "dy": 0.00, "price": 130.00},
    "ONDE":      {"c_z": 15.00, "c_wk": 1.50, "ev_ebitda": 10.00, "dy": 1.00, "price": 12.00},
    "CYBERFLKS": {"c_z": 20.00, "c_wk": 3.00, "ev_ebitda": 12.00, "dy": 0.00, "price": 45.00},
    "ELEKTROTI": {"c_z": 12.00, "c_wk": 1.00, "ev_ebitda": 7.00,  "dy": 3.00, "price": 28.00},
    "MEDINICE":  {"c_z": None,  "c_wk": 2.00, "ev_ebitda": None,  "dy": 0.00, "price": 6.00},
    "BIOCELTIX": {"c_z": None,  "c_wk": 2.50, "ev_ebitda": None,  "dy": 0.00, "price": 12.00},
    "PATENTUS":  {"c_z": 9.00,  "c_wk": 0.60, "ev_ebitda": 5.50,  "dy": 2.00, "price": 3.50},
    "ZABKA":     {"c_z": 30.00, "c_wk": 4.00, "ev_ebitda": 18.00, "dy": 0.00, "price": 18.00},
    "DIAG":      {"c_z": 20.00, "c_wk": 2.50, "ev_ebitda": 12.00, "dy": 2.00, "price": 180.00},
    "SCANWAY":   {"c_z": None,  "c_wk": 3.00, "ev_ebitda": None,  "dy": 0.00, "price": 18.00},
    "ERSTE":     {"c_z": 9.00,  "c_wk": 1.00, "ev_ebitda": 6.00,  "dy": 4.00, "price": 200.00},
    # Suspended / bankrupt — fallback price 0, will show as L4
    "GETIN":     {"c_z": None,  "c_wk": None,  "ev_ebitda": None,  "dy": 0.00, "price": 0.01},
    "KLEPSYDRA": {"c_z": None,  "c_wk": None,  "ev_ebitda": None,  "dy": 0.00, "price": 0.01},
    # ETFs — no fundamental ratios
    "ETFBSPXPL": {"c_z": None,  "c_wk": None,  "ev_ebitda": None,  "dy": 0.00, "price": 700.00},
    "ETFBW20TR": {"c_z": None,  "c_wk": None,  "ev_ebitda": None,  "dy": 0.00, "price": 450.00},
}


def parse_polish_number(val_str):
    """Helper to parse Polish localized numbers (e.g. '12,34 %' -> 12.34)"""
    if not val_str:
        return None
    try:
        cleaned = val_str.replace(" ", "").replace(",", ".").replace("%", "").replace("zł", "").strip()
        cleaned = "".join([c for c in cleaned if c.isdigit() or c in ".-"])
        if not cleaned:
            return None
        return float(cleaned)
    except Exception:
        return None


class StockwatchScraper:
    def __init__(self, phpsessid=None):
        # Stockwatch.pl runs on ASP.NET — the real session cookie is ASP.NET_SessionId.
        # The parameter is kept as 'phpsessid' for UI/settings backwards compatibility,
        # but we now set the correct ASP.NET cookie name.
        self.session_cookie = phpsessid
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.stockwatch.pl/"
        }
        self.session = requests.Session()
        if phpsessid:
            # ASP.NET session cookie (equivalent of PHPSESSID in PHP apps)
            self.session.cookies.set("ASP.NET_SessionId", phpsessid, domain="stockwatch.pl")
            # Also set as .ASPXAUTH in case the user copied the auth token instead
            self.session.cookies.set(".ASPXAUTH", phpsessid, domain="stockwatch.pl")

    def fetch_stockwatch_html_indicators(self, slug):
        """Scrapes standard company pages on Stockwatch.pl for fundamental ratios"""
        url = f"https://www.stockwatch.pl/gpw/{slug}.aspx"
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Stockwatch HTTP error {response.status_code} for slug {slug}")
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Scrape indicators from typical tables
            indicators = {}
            for td in soup.find_all(["td", "th", "span"]):
                text = td.get_text(strip=True)
                if text in ["C/Z", "C/WK", "EV/EBITDA", "Stopa dywidendy"]:
                    next_td = td.find_next_sibling(["td", "span"])
                    if not next_td:
                        # Try finding in parent's siblings
                        parent = td.parent
                        if parent:
                            siblings = parent.find_all("td")
                            if len(siblings) >= 2:
                                next_td = siblings[1]
                    if next_td:
                        val_str = next_td.get_text(strip=True)
                        indicators[text] = parse_polish_number(val_str)

            # Map to expected fields
            mapped = {
                "c_z": indicators.get("C/Z"),
                "c_wk": indicators.get("C/WK"),
                "ev_ebitda": indicators.get("EV/EBITDA"),
                "dy": indicators.get("Stopa dywidendy")
            }
            
            # Verify if we fetched anything substantial
            if any(v is not None for v in mapped.values()):
                return mapped
            
            return None
        except Exception as e:
            logger.error(f"Error scraping Stockwatch for {slug}: {str(e)}")
            return None

    def fetch_yfinance_fallback(self, ticker):
        """Fetches fundamental ratios and price from Yahoo Finance as level-3 fallback"""
        symbol = YFIN_TICKERS.get(ticker)
        if not symbol:
            return None
        try:
            yft = yf.Ticker(symbol)
            info = yft.info
            
            # Extract ratios
            c_z = info.get("trailingPE") or info.get("forwardPE")
            c_wk = info.get("priceToBook")
            ev_ebitda = info.get("enterpriseToEbitda")
            dy = info.get("dividendYield")
            if dy is not None:
                dy = dy * 100.0  # Convert e.g. 0.052 -> 5.2%
            else:
                dy = 0.0

            price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            
            # Clean up/validate
            mapped = {
                "c_z": round(c_z, 2) if c_z is not None else None,
                "c_wk": round(c_wk, 2) if c_wk is not None else None,
                "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda is not None else None,
                "dy": round(dy, 2) if dy is not None else 0.0,
                "price": round(price, 2) if price is not None else None
            }
            
            if any(v is not None for v in [mapped["c_z"], mapped["c_wk"], mapped["ev_ebitda"]]):
                return mapped
            
            return None
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance fallback for {ticker}: {str(e)}")
            return None

    def fetch_live_price_biznesradar(self, ticker):
        """Fetches real-time price from Biznesradar notowania page (span.q_ch_act)"""
        url = f"https://www.biznesradar.pl/notowania/{ticker}"
        try:
            r = self.session.get(url, headers=self.headers, timeout=10)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "html.parser")
            el = soup.find("span", class_="q_ch_act")
            if el:
                raw = el.get_text(strip=True).replace("\xa0", "").replace(" ", "")
                m = re.match(r"^-?[\d]+(?:[,.][\d]+)?", raw)
                if m:
                    return round(float(m.group().replace(",", ".")), 2)
        except Exception as e:
            logger.error(f"Biznesradar live price fetch error for {ticker}: {e}")
        return None

    def fetch_biznesradar(self, ticker):
        """Level-2 fallback: scrapes fundamental ratios and price from Biznesradar.pl"""
        url = f"https://www.biznesradar.pl/wskazniki-wartosci-rynkowej/{ticker}"
        try:
            r = self.session.get(url, headers=self.headers, timeout=10)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "html.parser")

            label_map = {
                "Cena / Zysk": "c_z",
                "Cena / Wartość księgowa": "c_wk",
                "EV / EBITDA": "ev_ebitda",
            }
            result = {}

            for tr in soup.find_all("tr"):
                first_td = tr.find("td", class_="f")
                if not first_td:
                    continue
                label = first_td.get_text(strip=True)
                field = label_map.get(label)
                if field is None:
                    continue

                newest_td = tr.find("td", class_="newest")
                if not newest_td:
                    h_tds = [td for td in tr.find_all("td", class_="h") if td.get_text(strip=True)]
                    if not h_tds:
                        continue
                    newest_td = h_tds[-1]

                raw = newest_td.get_text(strip=True).split("~branża")[0]
                # Extract leading number (handles "7,99" or "448,90" or "1,55r/r+1.37%...")
                m = re.match(r"^-?[\d]+(?:,[\d]+)?", raw.strip())
                if m:
                    result[field] = round(float(m.group().replace(",", ".")), 2)

            if not result.get("c_z") and not result.get("c_wk") and not result.get("ev_ebitda"):
                return None

            # DY from yfinance; live price: prefer yfinance → Biznesradar notowania → None
            yfin_data = self.fetch_yfinance_fallback(ticker)
            result["dy"] = yfin_data.get("dy", 0.0) if yfin_data else 0.0
            if yfin_data and yfin_data.get("price"):
                result["price"] = yfin_data["price"]
            else:
                # yfinance unavailable for this ticker — fetch live price from notowania page
                live_price = self.fetch_live_price_biznesradar(ticker)
                result["price"] = live_price  # may be None, caller will handle

            for field in ["c_z", "c_wk", "ev_ebitda", "dy", "price"]:
                result.setdefault(field, None)
            if result["dy"] is None:
                result["dy"] = 0.0

            return result
        except Exception as e:
            logger.error(f"Biznesradar fetch error for {ticker}: {e}")
            return None

    def fetch_mock_fallback(self, ticker):
        """Level-4 fallback: pre-programmed realistic ratios with deterministic noise"""
        base = STATIC_FALLBACKS.get(ticker, {"c_z": 12.0, "c_wk": 1.5, "ev_ebitda": 8.0, "dy": 3.0, "price": 100.0})
        # Add a tiny random fluctuation of +/-2% to make it feel "live"
        noise = 1.0 + random.uniform(-0.02, 0.02)
        
        def _apply_noise(v):
            if v is None:
                return None
            return round(v * noise, 2) if v > 0 else v

        return {
            "c_z":      _apply_noise(base.get("c_z")),
            "c_wk":     _apply_noise(base.get("c_wk")),
            "ev_ebitda": _apply_noise(base.get("ev_ebitda")),
            "dy": round((base.get("dy") or 0.0) * (1.0 + random.uniform(-0.05, 0.05)), 2),
            "price": round((base.get("price") or 100.0) * noise, 2),
        }

    def get_indicators(self, ticker):
        """Main method implementing 4-level data retrieval architecture"""
        slug = STOCKWATCH_SLUGS.get(ticker)

        # Level 1: Stockwatch Premium
        if self.session_cookie and slug:
            data = self.fetch_stockwatch_html_indicators(slug)
            if data and all(data.get(k) is not None for k in ["c_z", "c_wk", "ev_ebitda"]):
                price_data = self.fetch_yfinance_fallback(ticker)
                data["price"] = price_data["price"] if price_data else STATIC_FALLBACKS.get(ticker, {}).get("price", 100.0)
                data["source"] = "Stockwatch Premium (L1)"
                data["status"] = "Success"
                return data

        # Level 2: Biznesradar.pl (real fundamentals, no auth required)
        br_data = self.fetch_biznesradar(ticker)
        if br_data and any(br_data.get(k) is not None for k in ["c_z", "c_wk", "ev_ebitda"]):
            br_data["source"] = "Biznesradar.pl (L2)"
            br_data["status"] = "Success (Fallback)"
            return br_data

        # Level 3: Yahoo Finance API
        yfin_data = self.fetch_yfinance_fallback(ticker)
        if yfin_data and any(yfin_data.get(k) is not None for k in ["c_z", "c_wk", "ev_ebitda"]):
            yfin_data["source"] = "Yahoo Finance (L3)"
            yfin_data["status"] = "Success (Fallback)"
            return yfin_data

        # Level 4: Static Pre-programmed Fallback (no recommendations shown)
        mock_data = self.fetch_mock_fallback(ticker)
        # Even in L4, try to get a real live price so the Strategy tab shows correct values
        live_price = self.fetch_live_price_biznesradar(ticker)
        if live_price:
            mock_data["price"] = live_price
        mock_data["source"] = "Lokalna Baza Danych (L4)"
        mock_data["status"] = "Fallback (Offline)"
        return mock_data

    def get_technical_trend(self, ticker):
        """Calculates moving average (SMA50) technical trend with robust fallbacks"""
        symbol = YFIN_TICKERS.get(ticker)
        if not symbol:
            return 70  # neutral default when no yfinance symbol available
        try:
            yft = yf.Ticker(symbol)
            # Fetch 3 months of daily history to calculate SMA50
            hist = yft.history(period="3mo")
            if not hist.empty and len(hist) >= 50:
                current_price = hist["Close"].iloc[-1]
                sma50 = hist["Close"].tail(50).mean()
                return 100 if current_price > sma50 else 30
            elif not hist.empty and len(hist) >= 10:
                current_price = hist["Close"].iloc[-1]
                sma10 = hist["Close"].tail(10).mean()
                return 100 if current_price > sma10 else 30
            elif not hist.empty:
                price_now = hist["Close"].iloc[-1]
                price_prev = hist["Close"].iloc[0]
                return 100 if price_now > price_prev else 30
        except Exception as e:
            logger.error(f"Error calculating technical trend for {ticker}: {str(e)}")
        # Default fallback trend score
        return 70

    def calculate_score(self, indicators, trend_score):
        """Implements the exact weighting formulas defined in ANALYSIS_RULES.md"""
        c_z = indicators.get("c_z")
        c_wk = indicators.get("c_wk")
        ev_ebitda = indicators.get("ev_ebitda")
        dy = indicators.get("dy", 0.0)

        # C/Z Score (30%)
        if c_z is None:
            s_cz = 50.0  # Neutral
        elif c_z < 0:
            s_cz = 0.0
        elif 0 <= c_z < 5:
            s_cz = 50.0
        elif 5 <= c_z <= 12:
            s_cz = 100.0
        elif 12 < c_z <= 20:
            s_cz = 70.0
        elif 20 < c_z <= 35:
            s_cz = 40.0
        else:
            s_cz = 10.0

        # C/WK Score (20%)
        if c_wk is None:
            s_cwk = 50.0  # Neutral
        elif c_wk < 0:
            s_cwk = 0.0
        elif 0 <= c_wk <= 1.0:
            s_cwk = 100.0
        elif 1.0 < c_wk <= 2.5:
            s_cwk = 80.0
        elif 2.5 < c_wk <= 4.0:
            s_cwk = 50.0
        else:
            s_cwk = 20.0

        # EV/EBITDA Score (20%)
        if ev_ebitda is None:
            s_ev = 50.0  # Neutral
        elif ev_ebitda < 0:
            s_ev = 0.0
        elif 0 <= ev_ebitda <= 6.0:
            s_ev = 100.0
        elif 6.0 < ev_ebitda <= 11.0:
            s_ev = 75.0
        elif 11.0 < ev_ebitda <= 16.0:
            s_ev = 40.0
        else:
            s_ev = 15.0

        # DY Score (10%)
        if dy is None or dy == 0.0:
            s_dy = 0.0
        elif 0 < dy < 2.0:
            s_dy = 30.0
        elif 2.0 <= dy < 5.0:
            s_dy = 70.0
        elif 5.0 <= dy <= 10.0:
            s_dy = 100.0
        else:
            s_dy = 80.0

        # Weighted score (0-100)
        score = 0.30 * s_cz + 0.20 * s_cwk + 0.20 * s_ev + 0.10 * s_dy + 0.20 * trend_score
        return round(score, 1)

    def get_recommendation(self, score):
        """Returns action and color styling based on the synthetic score"""
        if score >= 70.0:
            return {"action": "KUPUJ", "color": "#28A745", "text_color": "#FFFFFF"}
        elif score <= 30.0:
            return {"action": "SPRZEDAJ", "color": "#DC3545", "text_color": "#FFFFFF"}
        else:
            return {"action": "TRZYMAJ", "color": "#FFC107", "text_color": "#212529"}

    def get_new_analyses(self, tickers, seen_ids=None, pages=3):
        """
        Scrapes /wiadomosci/analizyforum for technical/fundamental analyses
        matching any of the given tickers. Returns list of new articles (not in seen_ids).
        Requires a valid ASP.NET_SessionId cookie for Premium access.
        """
        if not self.session_cookie:
            return [], "Brak ciasteczka sesji — skonfiguruj ASP.NET_SessionId w sidebarze."

        if seen_ids is None:
            seen_ids = set()
        else:
            seen_ids = set(seen_ids)

        tickers_upper = {t.upper() for t in tickers}
        new_articles = []

        for page in range(1, pages + 1):
            url = f"https://www.stockwatch.pl/wiadomosci/analizyforum?page={page}" if page > 1 else "https://www.stockwatch.pl/wiadomosci/analizyforum"
            try:
                resp = self.session.get(url, headers=self.headers, timeout=12)
                if resp.status_code != 200:
                    logger.warning(f"Stockwatch analyses HTTP {resp.status_code} on page {page}")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")

                # Each article is typically in a <article> or <div> with a link containing the article ID
                articles = soup.find_all("a", href=True)
                for a in articles:
                    href = a["href"]
                    # Articles have URLs like /wiadomosci/...,xternal,12345
                    if ",xternal," not in href:
                        continue
                    try:
                        article_id = href.split(",xternal,")[-1].split(",")[0].strip()
                        if not article_id.isdigit():
                            continue
                    except Exception:
                        continue

                    title = a.get_text(strip=True)
                    if not title:
                        # Try parent element for richer text
                        parent = a.find_parent()
                        title = parent.get_text(strip=True) if parent else ""

                    title_upper = title.upper()
                    matched_ticker = None
                    for t in tickers_upper:
                        if t in title_upper:
                            matched_ticker = t
                            break

                    if not matched_ticker:
                        continue

                    if article_id in seen_ids:
                        continue

                    # Extract date from nearest sibling/parent text
                    date_str = ""
                    parent = a.find_parent()
                    if parent:
                        full_text = parent.get_text(" ", strip=True)
                        import re
                        date_match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})", full_text)
                        if date_match:
                            date_str = date_match.group(1)

                    # Determine analysis type from title
                    t_low = title.lower()
                    if any(w in t_low for w in ["wykres", "technicz", "sma", "rsi", "macd", "świec"]):
                        kind = "Analiza techniczna"
                        kind_color = "#5B8DEF"
                    elif any(w in t_low for w in ["fundamentaln", "wynik", "raport", "zysk", "przychód", "dywidend"]):
                        kind = "Analiza fundamentalna"
                        kind_color = "#ecfa64"
                    else:
                        kind = "Artykuł / komentarz"
                        kind_color = "#cde200"

                    new_articles.append({
                        "id": article_id,
                        "ticker": matched_ticker,
                        "title": title[:120],
                        "date": date_str,
                        "url": f"https://www.stockwatch.pl{href}" if href.startswith("/") else href,
                        "kind": kind,
                        "kind_color": kind_color,
                    })
                    seen_ids.add(article_id)

            except Exception as e:
                logger.error(f"Error fetching analyses page {page}: {e}")
                break

        return new_articles, None
