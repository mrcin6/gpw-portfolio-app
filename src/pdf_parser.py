import re
import pdfplumber

def parse_erste_pdf(pdf_path):
    """
    Parses quarterly reports (Kwartalne zestawienie aktywów) and financial instrument reports (Instrumenty finansowe raport)
    from Erste Biuro Maklerskie.
    Returns a dictionary with summary metrics and a list of holdings.
    """
    total_val = None
    cash_val = 0.0
    stocks_val = None
    report_date = None
    holdings = []

    with pdfplumber.open(pdf_path) as pdf:
        text_full = ""
        for page in pdf.pages:
            text_full += page.extract_text() + "\n"

    # Let's detect which format it is:
    # Format A: Kwartalne zestawienie aktywów (Q1 / Q2 2026)
    # Format B: Instrumenty finansowe raport (August 2026)
    
    is_format_b = "INSTRUMENTY FINANSOWE RAPORT" in text_full

    if is_format_b:
        # 1. Extract report date
        # Pattern: Stan na: 2026-08-23 18:58:20
        date_match = re.search(r"Stan na:\s*([\d]{4}-[\d]{2}-[\d]{2})", text_full)
        if date_match:
            report_date = date_match.group(1)

        # 2. Extract total stock valuation
        # Pattern: Instrumenty finansowe razem PLN: 132 692,06
        tot_match = re.search(r"Instrumenty finansowe razem PLN:\s*([\d\s]+,[\d]{2})", text_full)
        if tot_match:
            stocks_val = float(tot_match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
            total_val = stocks_val
            cash_val = 0.0  # Usually 0 or not in this specific instruments report

        # 3. Extract positions
        # In Format B, we have a line like:
        # DEKPOL 12 0 12 72,00 PLN 864,00 PLN 864,00 PLN
        # followed by ISIN: PLDEKPL00032 on the next line or nearby
        lines = text_full.split("\n")
        for i, line in enumerate(lines):
            isin_match = re.search(r"ISIN:\s*(PL[A-Z0-9]{10})", line)
            if isin_match:
                isin = isin_match.group(1)
                # Look at previous lines (up to 3 lines back) to find the ticker and quantity
                for j in range(1, 4):
                    if i - j >= 0:
                        prev_line = lines[i - j].strip()
                        # Match: <TICKER> <qty> <blocked> <rights> <price> PLN <val_foreign> PLN <val_pln> PLN
                        # E.g. DEKPOL 12 0 12 72,00 PLN 864,00 PLN 864,00 PLN
                        # Or ETFBSPXPL 5 0 5 132,60 PLN 663,00 PLN 663,00 PLN
                        pos_match = re.match(r"^([A-Z0-9\-]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d\s]+,[\d]+)\s+PLN\s+([\d\s]+,[\d]+)\s+PLN\s+([\d\s]+,[\d]+)\s+PLN", prev_line)
                        if pos_match:
                            ticker = pos_match.group(1)
                            qty = int(pos_match.group(2))
                            price = float(pos_match.group(5).replace(" ", "").replace(",", "."))
                            val = float(pos_match.group(7).replace(" ", "").replace(",", "."))
                            
                            # Deduplicate if already added
                            if not any(h['ticker'] == ticker for h in holdings):
                                holdings.append({
                                    "ticker": ticker,
                                    "isin": isin,
                                    "quantity": qty,
                                    "price": price,
                                    "valuation": val
                                })
                            break

    else:
        # Format A: Kwartalne zestawienie aktywów
        # 1. Extract report date
        # Pattern: Stan rachunku finansowego i rachunku papierów wartościowych na 31.03.2026
        date_match = re.search(r"wartościowych na\s+([\d]{2}\.[\d]{2}\.[\d]{4})", text_full)
        if date_match:
            report_date = date_match.group(1)
            # convert DD.MM.YYYY to YYYY-MM-DD
            parts = report_date.split(".")
            report_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

        # 2. Extract total value, cash value, stock valuation
        tot_match = re.search(r"Całkowita wartość rachunku:\s*([\d\s]+,[\d]{2})\s*PLN", text_full)
        if tot_match:
            total_val = float(tot_match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
            
        cash_match = re.search(r"Wartość pieniędzy:\s*([\d\s]+,[\d]{2})\s*PLN", text_full)
        if cash_match:
            cash_val = float(cash_match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
            
        stocks_match = re.search(r"Wycena papierów wartościowych:\s*([\d\s]+,[\d]{2})\s*PLN", text_full)
        if stocks_match:
            stocks_val = float(stocks_match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))

        # 3. Extract positions (Table 2)
        # Reassemble split lines
        lines = text_full.split("\n")
        reassembled_lines = []
        skip_next = False
        
        for i in range(len(lines)):
            if skip_next:
                skip_next = False
                continue
                
            line = lines[i].strip()
            # If line is ISIN (PL followed by 10 digits/chars) and next line starts with a digit/chars
            if re.match(r"^PL[A-Z0-9]{9,11}$", line) and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Check if next line contains a digit and starts with the remaining ISIN character
                # We merge them
                line = line + " " + next_line
                skip_next = True
            reassembled_lines.append(line)

        # Now search reassembled lines for positions
        for line in reassembled_lines:
            # Look for lines starting with combined ISIN, e.g. "PLDMDVL0001 2 DOMDEV 46 0 46 46 WWA 225,0"
            # Or "PLGRODN000 15 GRODNO 440..." -> which was split and reassembled into: "PLGRODN000 15 GRODNO 440 0 440 440 WWA 13,40"
            # Pattern: ISIN (with space) + remaining digits + Ticker + numbers...
            # Actually, let's write a regex to match the combined start
            match = re.match(r"^(PL[A-Z0-9]{9,11})\s+(\d+)\s+([A-Z0-9\-]+)\s+(\d+)", line)
            if match:
                partial_isin = match.group(1)
                last_digit = match.group(2)
                ticker = match.group(3)
                qty = int(match.group(4))
                isin = partial_isin + last_digit
                
                # Let's try to extract price and valuation
                # After the ticker and quantity, we have: blocked_qty, total_qty, rights, exchange ("WWA"), price
                # E.g., "PLDMDVL0001 2 DOMDEV 46 0 46 46 WWA 225,0"
                # Price is after "WWA"
                price = 0.0
                valuation = 0.0
                price_match = re.search(r"WWA\s+([\d\s]+,[\d]+)", line)
                if price_match:
                    price = float(price_match.group(1).replace(" ", "").replace(",", "."))
                
                # Valuation might be further in the text or we can calculate it as price * qty
                valuation = qty * price
                
                # Add to holdings
                if qty > 0:
                    holdings.append({
                        "ticker": ticker,
                        "isin": isin,
                        "quantity": qty,
                        "price": price,
                        "valuation": valuation
                    })

    # Return result
    return {
        "report_date": report_date,
        "total_value": total_val,
        "cash_value": cash_val,
        "stocks_value": stocks_val,
        "holdings": holdings
    }

if __name__ == "__main__":
    # Quick test if run directly
    import sys
    if len(sys.argv) > 1:
        res = parse_erste_pdf(sys.argv[1])
        print(res)
