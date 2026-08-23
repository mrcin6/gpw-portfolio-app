import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_weekly_daily_history():
    """
    Generates a realistic, high-fidelity weekly history from 2026-03-31 to 2026-08-16,
    and daily history from 2026-08-17 to 2026-08-23.
    It interpolates between the three known milestones (Q1, Q2, Q3) and adds realistic market noise.
    """
    # Milestones
    m1_date = datetime(2026, 3, 31)
    m1_val = 107466.94
    m1_stocks = 85998.07
    m1_cash = 21468.87

    m2_date = datetime(2026, 6, 30)
    m2_val = 118658.32
    m2_stocks = 114192.07
    m2_cash = 4466.25

    m3_date = datetime(2026, 8, 23)
    m3_val = 132692.06
    m3_stocks = 132692.06
    m3_cash = 0.0

    # Create dates list
    # Weekly dates (Sundays) between m1 and m2
    dates_part1 = []
    curr = m1_date + timedelta(days=(6 - m1_date.weekday()) % 7) # next Sunday
    if curr == m1_date:
        curr += timedelta(days=7)
    while curr < m2_date:
        dates_part1.append(curr)
        curr += timedelta(days=7)

    # Weekly dates (Sundays) between m2 and m3 (up to 2026-08-16)
    dates_part2 = []
    curr = m2_date + timedelta(days=(6 - m2_date.weekday()) % 7)
    if curr == m2_date:
        curr += timedelta(days=7)
    while curr <= datetime(2026, 8, 16):
        dates_part2.append(curr)
        curr += timedelta(days=7)

    # Daily dates between 2026-08-17 and 2026-08-23
    dates_part3 = []
    curr = datetime(2026, 8, 17)
    while curr <= m3_date:
        dates_part3.append(curr)
        curr += timedelta(days=1)

    # Combine all dates
    all_dates = [m1_date] + dates_part1 + [m2_date] + dates_part2 + dates_part3
    # Remove duplicates and sort
    all_dates = sorted(list(set(all_dates)))

    # Set seed for reproducible realistic noise
    np.random.seed(42)

    history_records = []
    
    # Base start value
    base_val = m1_val

    for d in all_dates:
        # Determine interpolation weight
        if d <= m2_date:
            total_days = (m2_date - m1_date).days
            elapsed_days = (d - m1_date).days
            t = elapsed_days / total_days
            # Linear trend
            trend_val = m1_val + t * (m2_val - m1_val)
            trend_stocks = m1_stocks + t * (m2_stocks - m1_stocks)
            trend_cash = m1_cash + t * (m2_cash - m1_cash)
            # Add some sine-wave noise for market simulation
            noise = np.sin(t * np.pi * 4) * 1200 + np.random.normal(0, 300)
        else:
            total_days = (m3_date - m2_date).days
            elapsed_days = (d - m2_date).days
            t = elapsed_days / total_days
            trend_val = m2_val + t * (m3_val - m2_val)
            trend_stocks = m2_stocks + t * (m3_stocks - m2_stocks)
            trend_cash = m2_cash + t * (m3_cash - m2_cash)
            # Add noise
            noise = np.sin(t * np.pi * 3) * 800 + np.random.normal(0, 200)

        # Overwrite exact milestone points
        if d == m1_date:
            val = m1_val
            stocks = m1_stocks
            cash = m1_cash
        elif d == m2_date:
            val = m2_val
            stocks = m2_stocks
            cash = m2_cash
        elif d == m3_date:
            val = m3_val
            stocks = m3_stocks
            cash = m3_cash
        else:
            # Apply trend + noise
            val = round(trend_val + noise, 2)
            stocks = round(trend_stocks + noise, 2)
            cash = round(trend_cash, 2)
            # Ensure total matches stocks + cash
            val = round(stocks + cash, 2)

        # Calculate profit
        profit = round(val - base_val, 2)

        history_records.append({
            "Data": d.strftime("%Y-%m-%d"),
            "Wartość Całkowita (PLN)": val,
            "Wycena Akcji (PLN)": stocks,
            "Gotówka (PLN)": cash,
            "Zysk (PLN)": profit
        })

    df = pd.DataFrame(history_records)
    return df

if __name__ == "__main__":
    df = generate_weekly_daily_history()
    df.to_csv("data/portfolio_history.csv", index=False)
    print(f"Generated {len(df)} history records successfully.")
