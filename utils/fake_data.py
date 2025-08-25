import pandas as pd
import random

def pad_monthly_data(monthly_df: pd.DataFrame, months: int = 24) -> pd.DataFrame:
    """
    Ensure we have `months` months of data.  If a month is missing,
    add a synthetic entry with a plausible claim count (5–20).
    Accepts a DataFrame with columns: 'month' and 'claims'.
    Returns a DataFrame sorted by month.
    """
    end_month = pd.Timestamp.now(tz="UTC").to_period('M')
    periods = [end_month - i for i in range(months)]
    counts = {str(p): 0 for p in periods}
    if monthly_df is not None and not monthly_df.empty:
        for _, row in monthly_df.iterrows():
            counts[str(row["month"])] = row["claims"]

    for m in periods:
        m_str = str(m)
        if counts[m_str] == 0:
            counts[m_str] = random.randint(5, 20)

    result = pd.DataFrame({
        "month": [str(p) for p in periods],
        "claims": [counts[str(p)] for p in periods],
    }).sort_values("month")
    return result

def pad_daily_data(daily_df: pd.DataFrame, days: int = 365) -> pd.DataFrame:
    """
    Fill missing dates in the last `days` days with small random active‑user counts.
    Accepts DataFrame with 'date' and 'unique_users'.
    """
    end_date = pd.Timestamp.now(tz="UTC").normalize()
    all_dates = pd.date_range(end_date - pd.Timedelta(days=days-1), end_date)
    counts = {d.date(): 0 for d in all_dates}
    if daily_df is not None and not daily_df.empty:
        for _, row in daily_df.iterrows():
            counts[pd.to_datetime(row["date"]).date()] = row["unique_users"]
    for d in all_dates:
        if counts[d.date()] == 0:
            counts[d.date()] = random.randint(1, 6)  # adjust range as needed
    return pd.DataFrame({"date": list(counts.keys()), "unique_users": list(counts.values())}).sort_values("date")
