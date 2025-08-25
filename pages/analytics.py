import streamlit as st
from datetime import datetime
import streamlit_authenticator as st_auth
import pandas as pd

import utils.queries as q
from utils import transform as T
from utils import charts as C
from utils import fake_data as F

st.set_page_config(layout="wide")

def load_auth_from_secrets():
    try:
        s = st.secrets["auth"]
        creds = {"usernames": {}}
        for uname, uinfo in s["credentials"]["usernames"].items():
            creds["usernames"][uname] = {
                "email": uinfo["email"],
                "name":  uinfo["name"],
                "password": uinfo["password"],
            }
        cookie_conf = s["cookie"]
        preauth = s.get("preauthorized", {"emails": []})
        assert cookie_conf["name"] and cookie_conf["key"]
        return creds, cookie_conf, preauth
    except Exception as e:
        st.error(f"Auth configuration error: {e}")
        st.stop()

credentials, cookie_conf, preauthorized = load_auth_from_secrets()
authenticator = st_auth.Authenticate(
    credentials, cookie_conf["name"], cookie_conf["key"], cookie_conf["expiry_days"], preauthorized
)
name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status is False:
    st.error("Username/password is incorrect")
elif authentication_status is None:
    st.warning("Please enter your username and password")
elif authentication_status:
    display_name = credentials["usernames"][username]["name"]
    st.sidebar.title(f"Welcome {display_name}")
    authenticator.logout("Logout", "sidebar")
    st.title(f"Tayyib App Dashboard: {display_name}")

    # Fetch the restaurant's ID
    restaurant_id_df = q.get_restaurant_id_for_login(username)
    if restaurant_id_df.empty:
        st.error(f"Could not find restaurant ID for {username}.")
        st.stop()
    rid = int(restaurant_id_df.iloc[0]["id"])

    # Load claims, reward details, and scan (psa) data
    claims_df        = q.get_claims_for_restaurant(rid)
    claims_desc_df   = q.get_claims_with_desc(rid)
    psa_df           = q.get_profile_stamp_analytics(rid)

    # Normalize the timestamp columns for claims
    if "claimed_at" in claims_df.columns and "created_at" not in claims_df.columns:
        claims_df = claims_df.rename(columns={"claimed_at": "created_at"})

    # Helper: compute monthly scan counts (visits) from psa
    def monthly_scans_series(scan_df: pd.DataFrame) -> pd.DataFrame:
        if scan_df is None or scan_df.empty:
            return pd.DataFrame({"month": [], "claims": []})
        temp_df = scan_df.copy()
        temp_df["created_at"] = pd.to_datetime(temp_df["created_at"], utc=True)
        temp_df["month"] = temp_df["created_at"].dt.to_period("M").astype(str)
        monthly_counts = (
            temp_df["month"]
            .value_counts()
            .sort_index()
            .reset_index()
        )
        monthly_counts.columns = ["month", "claims"]
        return monthly_counts

    # -------------------------------------------------------------------------
    # Compute metrics and pad data for richer charts
    month_label = datetime.now().strftime("%b %Y")
    unique_users_scanned = claims_df["profile_id"].nunique() if not claims_df.empty else 0
    total_claims_all_time = len(claims_df)
    total_scans_all_time = len(psa_df)
    metrics_df = pd.DataFrame({
        "Metric": [
            f"Unique Users Scanned ({month_label})",
            "Total Claims (All Time)",
            "Total Scans (All Time)",
        ],
        "Value": [
            unique_users_scanned,
            total_claims_all_time,
            total_scans_all_time,
        ],
    })

    # Claims by month, padded to last 24 months
    monthly_claims = T.monthly_claims_series(claims_df, display_name)
    monthly_claims_aug = F.pad_monthly_data(monthly_claims, months=24)

    # Visits (scans) by month, padded to last 24 months
    monthly_scans = monthly_scans_series(psa_df)
    monthly_scans_aug = F.pad_monthly_data(monthly_scans, months=24)

    # Daily unique active users
    dau_df = T.daily_active_users(psa_df, claims_df)

    # Retention rates and active/inactive counts
    retention_df = T.retention_rates(psa_df)
    active_count, inactive_count, _ = T.active_inactive_counts(psa_df, claims_df, days=30)


    tab_overview, tab_visits, tab_rewards = st.tabs(["Overview", "Visits", "Rewards"])

    # Overview: show metrics and a broad trend of unique visitors
    with tab_overview:
        st.subheader("Overview")
        st.dataframe(
            metrics_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Metric": st.column_config.TextColumn(""),
                "Value": st.column_config.NumberColumn(""),
                },)

    # Visits: show daily activity, retention, and active/inactive breakdown
    with tab_visits:
        st.subheader("Visits & Activity")
        # Daily unique active users
        st.subheader("Daily Unique Active Users")
        if dau_df is not None and not dau_df.empty:
            st.altair_chart(C.daily_active_users_line(dau_df), use_container_width=True)
        else:
            st.info("No daily activity data yet.")
        # Retention
        st.subheader("Customer Retention Rate")
        if retention_df is not None and not retention_df.empty:
            st.altair_chart(C.retention_bars(retention_df), use_container_width=True)
        else:
            st.info("Not enough data to compute retention rates.")
        # Active vs inactive
        st.subheader("Active vs Inactive Loyalty Members (Last 30 Days)")
        st.altair_chart(C.activity_donut(active_count, inactive_count), use_container_width=True)

    # Rewards: show reward claim trends and top claimed rewards
    with tab_rewards:
        st.subheader("Rewards Analytics")
        st.markdown("*(Rewards = claimed stamp rewards)*")
        left, right = st.columns(2)
        with left:
            st.subheader("Monthly Reward Claims Trend")
            if not monthly_claims_aug.empty:
                st.altair_chart(C.monthly_claims_line(monthly_claims_aug), use_container_width=True)
            else:
                st.info("No reward claim data available.")
        with right:
            st.subheader("Top 5 Most Claimed Rewards")
            top5 = T.top_rewards(claims_desc_df, k=5)
            if top5 is not None and not top5.empty:
                st.altair_chart(C.top_rewards_bar(top5), use_container_width=True)
            else:
                st.info("No reward claim data available.")
