# utils/transform.py
from __future__ import annotations
import pandas as pd
from typing import Iterable, List, Tuple

# ---- Small helpers ----------------------------------------------------------

def _ensure_dt(df: pd.DataFrame, cols: List[str]) -> str:
    """
    Find the first existing timestamp-like column and return its canonical name.
    We normalize to a column named 'ts' in UTC.
    """
    for c in cols:
        if c in df.columns:
            s = pd.to_datetime(df[c], utc=True, errors="coerce")
            df["ts"] = s
            return "ts"
    # If nothing found, create an empty ts
    df["ts"] = pd.NaT
    return "ts"

def _empty_df(columns: List[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="float64") for c in columns}).astype(
        {c: "int64" for c in columns if c in {"claims", "unique_users", "count"}}
    )

# ---- Public transformations --------------------------------------------------

def monthly_claims_series(claims_df: pd.DataFrame, restaurant_name: str) -> pd.DataFrame:
    """
    Input:
      claims_df columns minimally contain: profile_id, restaurant_name (opt), created_at or claimed_at
    Output:
      DataFrame with columns: month (YYYY-MM), claims (int)
    """
    if claims_df is None or claims_df.empty:
        return pd.DataFrame({"month": [], "claims": []})

    # If restaurant_name column not present (because we already filtered in SQL), skip the filter
    if "restaurant_name" in claims_df.columns:
        claims_df = claims_df[claims_df["restaurant_name"].str.lower() == restaurant_name.lower()].copy()

    ts_col = _ensure_dt(claims_df, ["created_at", "claimed_at"])
    if claims_df[ts_col].isna().all():
        return pd.DataFrame({"month": [], "claims": []})

    claims_df["month"] = claims_df[ts_col].dt.to_period("M").astype(str)
    out = (
        claims_df.groupby("month", dropna=True)
        .size()
        .reset_index(name="claims")
        .sort_values("month")
    )
    return out

def top_rewards(claims_with_desc_df: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """
    Input:
      claims_with_desc_df must contain 'description' (json/dict) for reward.
    Output:
      DataFrame: reward_summary, claims
    """
    if claims_with_desc_df is None or claims_with_desc_df.empty:
        return pd.DataFrame({"reward_summary": [], "claims": []})

    def _summary(x):
        # x may be dict/jsonb loaded into Python dict by psycopg2
        if isinstance(x, dict):
            en = x.get("en", {})
            return en.get("summary") or en.get("title") or "Unknown"
        return "Unknown"

    df = claims_with_desc_df.copy()
    df["reward_summary"] = df["description"].apply(_summary)
    out = (
        df["reward_summary"]
        .value_counts(dropna=False)
        .rename_axis("reward_summary")
        .reset_index(name="claims")
        .head(k)
    )
    # keep deterministic order (descending by count)
    out = out.sort_values(["claims", "reward_summary"], ascending=[False, True])
    return out

def daily_active_users(psa_df: pd.DataFrame, claims_df: pd.DataFrame) -> pd.DataFrame:
    """
    Active user = a profile that either scanned a stamp (psa_df) or claimed a reward (claims_df).
    Output:
      DataFrame: date (datetime64[ns]), unique_users (int)
    """
    frames = []

    if psa_df is not None and not psa_df.empty:
        df1 = psa_df[["profile_id"]].copy()
        ts1 = _ensure_dt(psa_df, ["created_at"])
        df1["ts"] = psa_df[ts1]
        frames.append(df1)

    if claims_df is not None and not claims_df.empty:
        df2 = claims_df[["profile_id"]].copy()
        ts2 = _ensure_dt(claims_df, ["created_at", "claimed_at"])
        df2["ts"] = claims_df[ts2]
        frames.append(df2)

    if not frames:
        return pd.DataFrame({"date": [], "unique_users": []})

    all_activity = pd.concat(frames, ignore_index=True)
    all_activity = all_activity.dropna(subset=["ts"])
    all_activity["date"] = all_activity["ts"].dt.date
    out = (
        all_activity.groupby("date")["profile_id"]
        .nunique()
        .reset_index(name="unique_users")
        .sort_values("date")
    )
    # convert to datetime for Altair temporal axis
    out["date"] = pd.to_datetime(out["date"])
    return out

def retention_rates(psa_df: pd.DataFrame, periods: Iterable[int] = (30, 60, 90)) -> pd.DataFrame:
    """
    Very simple retention:
      For each user, if any scan exists within N days AFTER their first scan -> retained.
    Input:
      psa_df needs columns: profile_id, created_at
    Output:
      DataFrame: period (e.g. '30 Days'), rate (0..100 float)
    """
    if psa_df is None or psa_df.empty:
        return pd.DataFrame({"period": [f"{p} Days" for p in periods], "rate": [0.0] * len(tuple(periods))})

    ts_col = _ensure_dt(psa_df, ["created_at"])
    df = psa_df.dropna(subset=[ts_col]).copy()

    # first scan per user
    first = df.groupby("profile_id")[ts_col].min().rename("first_scan")
    scans = df.groupby("profile_id")[ts_col].apply(list).rename("scans")
    merged = pd.concat([first, scans], axis=1).reset_index()

    results = []
    total = len(merged)
    for d in periods:
        retained = 0
        delta = pd.Timedelta(days=int(d))
        for _, row in merged.iterrows():
            fs = row["first_scan"]
            future_scans = [t for t in row["scans"] if (t > fs) and (t <= fs + delta)]
            if future_scans:
                retained += 1
        rate = (retained / total * 100.0) if total > 0 else 0.0
        results.append({"period": f"{int(d)} Days", "rate": rate})

    return pd.DataFrame(results)

def active_inactive_counts(psa_df: pd.DataFrame, claims_df: pd.DataFrame, days: int = 30) -> Tuple[int, int, int]:
    """
    Count active vs inactive members in the last `days`.
    Active = appeared in psa_df or claims_df within the rolling window ending 'now' (UTC).
    Returns: (active, inactive, total)
    """
    # All members ever seen
    members = set()

    # Timestamps normalized
    recent_cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(days))

    active = set()

    if psa_df is not None and not psa_df.empty:
        members.update(psa_df["profile_id"].unique())
        ts1 = _ensure_dt(psa_df, ["created_at"])
        active.update(psa_df.loc[psa_df[ts1] >= recent_cutoff, "profile_id"].unique())

    if claims_df is not None and not claims_df.empty:
        members.update(claims_df["profile_id"].unique())
        ts2 = _ensure_dt(claims_df, ["created_at", "claimed_at"])
        active.update(claims_df.loc[claims_df[ts2] >= recent_cutoff, "profile_id"].unique())

    total = len(members)
    active_n = len(active)
    inactive_n = max(total - active_n, 0)
    return active_n, inactive_n, total
