from __future__ import annotations
import altair as alt
import pandas as pd
from utils.ui import chart_frame, BASE_FONT, PALETTE

def monthly_compare_line(your_df: pd.DataFrame, all_df: pd.DataFrame) -> alt.Chart:
    # both inputs: columns month('YYYY-MM'), value(int)
    a = your_df.copy(); a["series"] = "Your restaurant"
    b = all_df.copy();  b["series"] = "All restaurants (avg)"

    df = pd.concat([a, b], ignore_index=True)
    df["month"] = pd.to_datetime(df["month"] + "-01", utc=True)

    c = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %y")),
            y=alt.Y("claims:Q", title=None),
            color=alt.Color("series:N", title=None),
            tooltip=[
                alt.Tooltip("series:N"),
                alt.Tooltip("month:T", format="%b %Y"),
                alt.Tooltip("claims:Q", title="Users"),
            ],
        )
    )
    return chart_frame(c)


def monthly_claims_line(monthly_claims: pd.DataFrame, *, title=None) -> alt.Chart:
    """
    Expects columns: month (string 'YYYY-MM') and claims (int).
    Renders with horizontal month labels like 'Aug 23', 'Sep 23', ...
    """
    if monthly_claims is None or monthly_claims.empty:
        c = alt.Chart(pd.DataFrame({"msg": ["No data"]})).mark_text(size=14).encode(text="msg:N")
        return chart_frame(c)

    df = monthly_claims.copy()
    # Convert 'YYYY-MM' -> month-start Timestamp; Altair temporal axis can format nicely.
    df["month"] = pd.to_datetime(df["month"] + "-01", utc=True)
    c = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %y")),  # e.g., 'Aug 25'
            y=alt.Y("claims:Q", title=None),
            tooltip=[alt.Tooltip("month:T", format="%b %Y"), alt.Tooltip("claims:Q", title="Claims")],
        )
    )
    return chart_frame(c)

def daily_active_users_line(dau: pd.DataFrame) -> alt.Chart:
    """
    Expects: date (datetime/date/iso) and unique_users (int).
    Dates shown horizontal as 'Aug 19', 'Aug 20', ...
    """
    if dau is None or dau.empty:
        c = alt.Chart(pd.DataFrame({"msg": ["No daily activity"]})).mark_text(size=14).encode(text="msg:N")
        return chart_frame(c)

    df = dau.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    c = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %d")),  # horizontal
            y=alt.Y("unique_users:Q", title=None),
            tooltip=[alt.Tooltip("date:T", format="%b %d, %Y"), alt.Tooltip("unique_users:Q", title="Users")],
        )
    )
    return chart_frame(c)

def top_rewards_bar(top_rewards: pd.DataFrame) -> alt.Chart:
    """
    Expects: reward_summary (str), claims (int).
    """
    if top_rewards is None or top_rewards.empty:
        c = alt.Chart(pd.DataFrame({"msg": ["No rewards claimed"]})).mark_text(size=14).encode(text="msg:N")
        return chart_frame(c)

    df = top_rewards.copy().sort_values("claims", ascending=True)
    c = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("claims:Q", title=None),
            y=alt.Y("reward_summary:N", title=None),
            tooltip=[alt.Tooltip("reward_summary:N", title="Reward"), alt.Tooltip("claims:Q", title="Claims")],
        )
    )
    return chart_frame(c)

def retention_bars(retention: pd.DataFrame) -> alt.Chart:
    """
    Expects: period (str like '30 Days'), rate (0..100).
    X axis labels kept flat (horizontal) for readability.
    """
    if retention is None or retention.empty:
        c = alt.Chart(pd.DataFrame({"msg": ["Not enough data to compute retention"]})).mark_text(size=14).encode(text="msg:N")
        return chart_frame(c)

    df = retention.copy()
    c = (
        alt.Chart(df)
        .mark_bar(size=40)
        .encode(
            x=alt.X("period:N", title=None, axis=alt.Axis(labelAngle=0)),  # flat labels
            y=alt.Y("rate:Q", title=None, scale=alt.Scale(domain=[0, 100])),
            tooltip=[alt.Tooltip("period:N", title="Window"), alt.Tooltip("rate:Q", title="Retention", format=".1f")],
        )
    )
    return chart_frame(c)

def activity_donut(active: int, inactive: int) -> alt.Chart:
    data = pd.DataFrame({"status": ["Active", "Inactive"], "count": [int(active), int(inactive)]})
    if data["count"].sum() == 0:
        c = alt.Chart(pd.DataFrame({"msg": ["No members found"]})).mark_text(size=14).encode(text="msg:N")
        return chart_frame(c)

    c = (
        alt.Chart(data)
        .mark_arc(innerRadius=70, outerRadius=110)
        .encode(
            theta="count:Q",
            color=alt.Color("status:N", legend=alt.Legend(title=None)),
            tooltip=[alt.Tooltip("status:N"), alt.Tooltip("count:Q", title="Members")],
        )
    )
    return chart_frame(c)
