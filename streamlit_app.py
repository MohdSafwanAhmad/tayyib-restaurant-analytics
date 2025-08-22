import streamlit as st
import pandas as pd
from datetime import datetime
import os
import streamlit_authenticator as st_auth
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import psycopg2

# --- Config ---
PLOTS_DIR = 'public/images/analytics_plots'
os.makedirs(PLOTS_DIR, exist_ok=True)

# Define a consistent color palette
PRIMARY_COLOR = '#4ECDC4' # Teal
SECONDARY_COLOR = '#FF6B6B' # Reddish-orange
ACCENT_COLOR = '#45B7D1' # Light blue
GRAY_COLOR = '#6c757d' # Muted gray

# Database connection details (fetched from environment variables)
PG_HOST = st.secrets.get("PG_HOST", os.environ.get("PG_HOST"))
PG_PORT = int(st.secrets.get("PG_PORT", os.environ.get("PG_PORT", 6543)))
PG_DBNAME = st.secrets.get("PG_DBNAME", os.environ.get("PG_DBNAME"))
PG_USER = st.secrets.get("PG_USER", os.environ.get("PG_USER"))
PG_PASSWORD = st.secrets.get("PG_PASSWORD", os.environ.get("PG_PASSWORD"))

# --- Database Functions ---
@st.cache_resource
def get_pg_connection():
  """Establishes and returns a PostgreSQL database connection."""
  try:
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DBNAME,
        user=PG_USER,
        password=PG_PASSWORD,
        sslmode="require"
    )
    return conn
  except Exception as e:
    st.error(f"Error connecting to the database: {e}")
    return None

@st.cache_data(ttl=3600) # Cache data for 1 hour
def get_data_as_dataframe(query, params=None):
  """
  Fetches data from PostgreSQL and returns it as a pandas DataFrame.
  Supports parameterized queries.
  """
  conn = None
  try:
    conn = get_pg_connection()
    if conn:
      df = pd.read_sql_query(query, conn, params=params)
      print(df)
      return df
    return pd.DataFrame()
  except Exception as e:
    st.error(f"Error fetching data: {e}")
    return pd.DataFrame()

# --- Data Preparation and Display Functions ---

def prepare_monthly_claims_data(df: pd.DataFrame, restaurant_name: str):
    """
    Prepares monthly reward claims data for a specific restaurant to be used with st.line_chart.

    Args:
        df (pd.DataFrame): The input DataFrame containing reward claims data.
                           Must include 'created_at' and 'restaurant_name' columns.
        restaurant_name (str): The name of the restaurant for which to prepare the data.

    Returns:
        pd.Series: A Series with month_year as index and number of claims as values,
                   or None if no data found for the restaurant.
    """
    if df.empty:
        return None

    restaurant_df = df[df['restaurant_name'].str.lower() == restaurant_name.lower()].copy()

    if restaurant_df.empty:
        return None # Return None silently for the overview metric if no data

    restaurant_df['created_at'] = pd.to_datetime(restaurant_df['created_at'], utc=True)
    restaurant_df['month_year'] = restaurant_df['created_at'].dt.to_period('M')

    monthly_claims = restaurant_df['month_year'].value_counts().sort_index()
    monthly_claims.index = monthly_claims.index.astype(str)
    monthly_claims.name = 'Number of Claims'

    return monthly_claims


def display_monthly_claims_trend_line_chart(df: pd.DataFrame, restaurant_name: str):
    """
    Line chart of monthly reward claims trend for a specific restaurant.
    Returns a matplotlib figure.
    """
    if df.empty:
        st.info(f"No claims data found for {restaurant_name}.")
        return None

    # Ensure 'created_at' column exists and is datetime
    if 'claimed_at' in df.columns and 'created_at' not in df.columns:
        df.rename(columns={'claimed_at': 'created_at'}, inplace=True)
    
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    df['month_year'] = df['created_at'].dt.to_period('M')

    monthly_claims = df['month_year'].value_counts().sort_index()
    monthly_claims.index = monthly_claims.index.astype(str)

    fig, ax = plt.subplots(figsize=(8, 4)) # Adjusted figure size
    sns.lineplot(x=monthly_claims.index, y=monthly_claims.values, marker='o', color=PRIMARY_COLOR, ax=ax)
    ax.set_title('Monthly Reward Claims Trend') # Simplified title
    ax.set_xlabel('Month')
    ax.set_ylabel('Number of Claims')
    plt.xticks(rotation=45)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    return fig

def display_total_unique_active_users_by_month_bar_chart(monthly_claims_data: pd.Series):
    """
    Bar chart of total unique active users by month.
    """
    if monthly_claims_data is None or monthly_claims_data.empty:
        st.info("No monthly unique active users data to plot.")
        return None

    fig, ax = plt.subplots(figsize=(9, 4.5)) # Adjusted figure size
    sns.barplot(x=monthly_claims_data.index, y=monthly_claims_data.values, color=PRIMARY_COLOR, ax=ax)
    ax.set_title('Total Unique Active Users by Month')
    ax.set_xlabel('Month')
    ax.set_ylabel('Number of Unique Users')
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    return fig


def display_most_claimed_rewards(df_claimed_rewards_with_desc: pd.DataFrame):
    """Bar chart of the top 5 most claimed rewards."""
    if df_claimed_rewards_with_desc.empty:
        st.info("No data to plot for most claimed rewards.")
        return None

    df_claimed_rewards_with_desc['reward_summary'] = df_claimed_rewards_with_desc['description'].apply(
        lambda x: x['en']['summary'] if pd.notna(x) and isinstance(x, dict) and 'en' in x and 'summary' in x['en'] else 'Unknown'
    )

    reward_counts = df_claimed_rewards_with_desc['reward_summary'].value_counts().head(5)

    if reward_counts.empty:
        st.info("No claimed rewards data available to determine top rewards.")
        return None

    fig, ax = plt.subplots(figsize=(7, 4)) # Adjusted figure size
    sns.barplot(x=reward_counts.values, y=reward_counts.index, color=ACCENT_COLOR, ax=ax) # Consistent color
    ax.set_title('Top 5 Most Claimed Rewards') # Simplified title
    ax.set_xlabel('Number of Claims')
    ax.set_ylabel('Reward Summary')
    plt.tight_layout()
    return fig

def display_daily_unique_active_users(df_profile_stamp_analytics: pd.DataFrame, df_claimed_stamp_rewards: pd.DataFrame):
    """
    Line chart of daily unique active users.
    Active users - those who either scanned a stamp or claimed a reward.
    """
    all_activity = pd.DataFrame()

    if not df_profile_stamp_analytics.empty:
        df_psa_temp = df_profile_stamp_analytics[['profile_id', 'created_at']].copy()
        df_psa_temp.rename(columns={'created_at': 'activity_time'}, inplace=True)
        all_activity = pd.concat([all_activity, df_psa_temp])

    if not df_claimed_stamp_rewards.empty:
        df_csr_temp = df_claimed_stamp_rewards[['profile_id', 'created_at']].copy()
        df_csr_temp.rename(columns={'created_at': 'activity_time'}, inplace=True)
        all_activity = pd.concat([all_activity, df_csr_temp])

    if all_activity.empty:
        st.info("No combined activity data available for daily unique active users.")
        return None

    all_activity['activity_time'] = pd.to_datetime(all_activity['activity_time'], utc=True)
    all_activity['activity_date'] = all_activity['activity_time'].dt.date

    daily_active_users = all_activity.groupby('activity_date')['profile_id'].nunique().reset_index()
    daily_active_users.columns = ['date', 'unique_users']
    daily_active_users['date'] = pd.to_datetime(daily_active_users['date'])
    daily_active_users.sort_values('date', inplace=True)

    if daily_active_users.empty:
        st.info("No daily active users data to plot.")
        return None

    fig, ax = plt.subplots(figsize=(9, 4.5)) # Adjusted figure size
    sns.lineplot(x='date', y='unique_users', data=daily_active_users, marker='o', color=SECONDARY_COLOR, ax=ax) # Consistent color
    ax.set_title('Daily Unique Active Users') # Simplified title
    ax.set_xlabel('Date')
    ax.set_ylabel('Number of Unique Users')
    plt.xticks(rotation=45)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    return fig

def display_customer_retention_rate(df_profile_stamp_analytics: pd.DataFrame):
    """
    Calculate and visualize basic customer retention rate.
    Shows percentage of customers who returned within specified days after their first scan.
    """
    if df_profile_stamp_analytics.empty:
        st.info("No stamp analytics data to plot for customer retention rate.")
        return None

    df_profile_stamp_analytics['created_at'] = pd.to_datetime(df_profile_stamp_analytics['created_at'], utc=True)

    first_scans = df_profile_stamp_analytics.groupby('profile_id')['created_at'].min().reset_index()
    first_scans.columns = ['profile_id', 'first_scan_date']

    all_scans = df_profile_stamp_analytics.groupby('profile_id')['created_at'].apply(list).reset_index()
    all_scans.columns = ['profile_id', 'scan_dates']

    customer_data = pd.merge(first_scans, all_scans, on='profile_id')

    retention_periods = [30, 60, 90]
    retention_rates = []

    for days in retention_periods:
        retained_customers = 0
        total_customers = len(customer_data)

        for _, row in customer_data.iterrows():
            first_scan = row['first_scan_date']
            scan_dates = row['scan_dates']

            retention_window = first_scan + pd.Timedelta(days=days)
            future_scans = [date for date in scan_dates if date > first_scan and date <= retention_window]

            if future_scans:
                retained_customers += 1

        retention_rate = (retained_customers / total_customers * 100) if total_customers > 0 else 0
        retention_rates.append(retention_rate)

    if not retention_rates:
        st.info("Not enough data to calculate retention rates.")
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5)) # Adjusted figure size

    # Bar chart showing retention rates for different periods
    bar_colors = [PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR] # Consistent color palette
    bars = ax1.bar([f'{days} Days' for days in retention_periods], retention_rates, color=bar_colors)
    ax1.set_title('Customer Retention Rate by Period') # Simplified title
    ax1.set_ylabel('Retention Rate (%)')
    ax1.set_ylim(0, 100)

    for bar, rate in zip(bars, retention_rates):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold')

    # Gauge-style visualization for 30-day retention
    retention_30 = retention_rates[0]

    theta = np.linspace(0, np.pi, 100)
    radius = 1

    ax2.plot(radius * np.cos(theta), radius * np.sin(theta), 'lightgray', linewidth=20)

    retention_theta = np.linspace(0, np.pi * (retention_30 / 100), max(2, int(retention_30)))
    if len(retention_theta) > 0:
        ax2.plot(radius * np.cos(retention_theta), radius * np.sin(retention_theta),
                bar_colors[0], linewidth=20) # Consistent color

    ax2.text(0, 0.2, f'{retention_30:.1f}%', ha='center', va='center',
             fontsize=24, fontweight='bold', color=bar_colors[0]) # Consistent color
    ax2.text(0, -0.1, '30-Day Retention', ha='center', va='center',
             fontsize=12, color=GRAY_COLOR)

    ax2.set_xlim(-1.2, 1.2)
    ax2.set_ylim(-0.2, 1.2)
    ax2.set_aspect('equal')
    ax2.axis('off')
    ax2.set_title('30-Day Customer Retention Rate', pad=20) # Simplified title

    plt.tight_layout()
    return fig

def display_active_vs_inactive_members(df_profile_stamp_analytics: pd.DataFrame, df_claimed_stamp_rewards: pd.DataFrame):
    """
    Visualize active vs inactive loyalty members.
    Shows proportion of members who have been active (scanned/claimed) in the last X days.
    """
    all_members = set()
    active_members = set()

    current_date = pd.Timestamp.now(tz='UTC')
    activity_days = 30 # Hardcode for this plot as it's a standard metric
    activity_cutoff = current_date - pd.Timedelta(days=activity_days)

    if not df_profile_stamp_analytics.empty:
        df_profile_stamp_analytics['created_at'] = pd.to_datetime(df_profile_stamp_analytics['created_at'], utc=True)
        all_members.update(df_profile_stamp_analytics['profile_id'].unique())

        recent_scanners = df_profile_stamp_analytics[
            df_profile_stamp_analytics['created_at'] >= activity_cutoff
        ]['profile_id'].unique()
        active_members.update(recent_scanners)

    if not df_claimed_stamp_rewards.empty:
        df_claimed_stamp_rewards['created_at'] = pd.to_datetime(df_claimed_stamp_rewards['created_at'], utc=True)
        all_members.update(df_claimed_stamp_rewards['profile_id'].unique())

        recent_claimers = df_claimed_stamp_rewards[
            df_claimed_stamp_rewards['created_at'] >= activity_cutoff
        ]['profile_id'].unique()
        active_members.update(recent_claimers)

    total_members = len(all_members)
    active_count = len(active_members)
    inactive_count = total_members - active_count

    if total_members == 0:
        st.info("No member activity data to plot for active vs inactive members.")
        return None

    active_percentage = (active_count / total_members * 100)
    inactive_percentage = (inactive_count / total_members * 100)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5)) # Adjusted figure size

    # Donut chart
    sizes = [active_count, inactive_count]
    labels = ['Active', 'Inactive']
    donut_colors = [PRIMARY_COLOR, SECONDARY_COLOR] # Consistent colors
    explode = (0.05, 0)

    wedges, texts, autotexts = ax1.pie(sizes, labels=labels, colors=donut_colors, autopct='%1.1f%%',
                                       startangle=90, explode=explode, pctdistance=0.85,
                                       wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2))

    ax1.text(0, 0, f'{total_members}\nTotal\nMembers', ha='center', va='center',
             fontsize=14, fontweight='bold', color=GRAY_COLOR)

    ax1.set_title(f'Active vs Inactive Members\n(Last {activity_days} Days)', fontsize=14, pad=20) # Simplified title

    # Large numbers display
    ax2.text(0.25, 0.7, f'{active_count}', ha='center', va='center',
             fontsize=48, fontweight='bold', color=donut_colors[0]) # Consistent color
    ax2.text(0.25, 0.55, 'ACTIVE', ha='center', va='center',
             fontsize=16, fontweight='bold', color=donut_colors[0]) # Consistent color
    ax2.text(0.25, 0.45, f'{active_percentage:.1f}%', ha='center', va='center',
             fontsize=16, color=donut_colors[0]) # Consistent color

    ax2.text(0.75, 0.7, f'{inactive_count}', ha='center', va='center',
             fontsize=48, fontweight='bold', color=donut_colors[1]) # Consistent color
    ax2.text(0.75, 0.55, 'INACTIVE', ha='center', va='center',
             fontsize=16, fontweight='bold', color=donut_colors[1]) # Consistent color
    ax2.text(0.75, 0.45, f'{inactive_percentage:.1f}%', ha='center', va='center',
             fontsize=16, color=donut_colors[1]) # Consistent color

    ax2.axvline(x=0.5, color='lightgray', linestyle='--', alpha=0.7)

    ax2.text(0.5, 0.2, f'Total Members: {total_members}', ha='center', va='center',
             fontsize=14, fontweight='bold', color=GRAY_COLOR)
    ax2.text(0.5, 0.1, f'Activity Period: Last {activity_days} Days', ha='center', va='center',
             fontsize=12, color=GRAY_COLOR)

    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.set_aspect('equal')
    ax2.axis('off')
    ax2.set_title('Member Activity Breakdown', fontsize=14, pad=20) # Simplified title

    plt.tight_layout()
    return fig

# --- Streamlit App Layout ---
st.set_page_config(layout="wide")

def load_auth_from_secrets():
    try:
        s = st.secrets["auth"]

        # Build the credentials dict expected by streamlit-authenticator
        creds = {"usernames": {}}
        for uname, uinfo in s["credentials"]["usernames"].items():
            creds["usernames"][uname] = {
                "email": uinfo["email"],
                "name":  uinfo["name"],
                "password": uinfo["password"],  # already hashed
            }

        cookie_conf = s["cookie"]
        preauth = s.get("preauthorized", {"emails": []})

        # sanity checks
        assert cookie_conf["name"] and cookie_conf["key"]
        return creds, cookie_conf, preauth
    except Exception as e:
        st.error(f"Auth configuration error: {e}")
        st.stop()

credentials, cookie_conf, preauthorized = load_auth_from_secrets()

authenticator = st_auth.Authenticate(
    credentials,
    cookie_conf["name"],
    cookie_conf["key"],
    cookie_conf["expiry_days"],
    preauthorized,
)

name, authentication_status, username = authenticator.login("Login", "main")

# --- Conditional Display based on Authentication Status ---
if authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
elif authentication_status:
    # User is logged in
    display_name = credentials["usernames"][username]["name"]
    st.sidebar.title(f"Welcome {display_name}")
    authenticator.logout("Logout", "sidebar") # Logout button in sidebar

    st.title(f"Tayyib App Dashboard: {display_name}") # Changed main title

    # --- Fetch Restaurant ID for the logged-in user ---
    restaurant_id_query = """
    SELECT id FROM public.restaurants WHERE name ILIKE %s;
    """
    restaurant_id_df = get_data_as_dataframe(restaurant_id_query, params=(username,))
    
    logged_in_restaurant_id = None
    if not restaurant_id_df.empty:
        logged_in_restaurant_id = restaurant_id_df.iloc[0]['id']
    else:
        st.error(f"Could not find restaurant ID for {username}. Please ensure the restaurant name in the database matches the login username.")
        st.stop() # Stop execution if restaurant ID cannot be determined

    # --- Fetch Data for the Logged-in Restaurant ---

    claimed_rewards_query = """
    SELECT
        csr.claimed_at,
        csr.profile_id,
        r.name AS restaurant_name
    FROM
        public.claimed_stamp_rewards csr
    JOIN
        public.restaurants r ON csr.restaurant_id = r.id
    WHERE
        csr.restaurant_id = %s
    ORDER BY
        csr.claimed_at;
    """
    claimed_rewards_df = get_data_as_dataframe(claimed_rewards_query, params=(int(logged_in_restaurant_id),))
    
    if 'claimed_at' in claimed_rewards_df.columns and 'created_at' not in claimed_rewards_df.columns:
        claimed_rewards_df.rename(columns={'claimed_at': 'created_at'}, inplace=True)


    claimed_rewards_with_desc_query = """
    SELECT
        csr.id,
        csr.profile_id,
        csr.restaurant_id,
        csr.claimed_at,
        csr.restaurant_stamp_reward_id,
        rsr.description
    FROM
        public.claimed_stamp_rewards csr
    JOIN
        public.restaurant_stamp_rewards rsr ON csr.restaurant_stamp_reward_id = rsr.id
    WHERE
        csr.restaurant_id = %s
    ORDER BY
        csr.claimed_at;
    """
    claimed_rewards_with_desc_df = get_data_as_dataframe(claimed_rewards_with_desc_query, params=(int(logged_in_restaurant_id),))

    profile_stamp_analytics_query = """
    SELECT
        profile_id,
        created_at
    FROM
        public.profile_stamp_analytics
    WHERE
        restaurant_id = %s
    ORDER BY
        created_at;
    """
    profile_stamp_analytics_df = get_data_as_dataframe(profile_stamp_analytics_query, params=(int(logged_in_restaurant_id),))

    # --- Display Plots for the Logged-in Restaurant ---
    logged_in_restaurant_name = display_name

    # Overall Metrics Section (as seen in your PDF)
    st.header("Overview")
    col1, col2, col3 = st.columns(3) # Reduced to 3 columns for metrics

    # Get current month and year for dynamic label
    current_month_year = datetime.now().strftime("%b %Y") # e.g., "Jul 2025"

    # Placeholder values for now, you'd fetch these from your DB
    unique_users_scanned_this_month = claimed_rewards_df['profile_id'].nunique() if not claimed_rewards_df.empty else 0
    total_claims_all_time = len(claimed_rewards_df) if not claimed_rewards_df.empty else 0
    total_scans_all_time = len(profile_stamp_analytics_df) if not profile_stamp_analytics_df.empty else 0
    
    # Prepare data for "Total Unique Active Users by Month" bar chart
    monthly_active_users_data = prepare_monthly_claims_data(claimed_rewards_df.copy(), logged_in_restaurant_name)


    with col1:
        st.metric(label=f"Unique Users Scanned ({current_month_year})", value=unique_users_scanned_this_month)
    with col2:
        st.metric(label="Total Claims (All Time)", value=total_claims_all_time)
    with col3:
        st.metric(label="Total Scans (All Time)", value=total_scans_all_time)
    
    # New row for the "Total Unique Active Users by Month" bar chart
    st.subheader("Total Unique Active Users by Month")
    with st.spinner(f"Generating plot..."):
        fig_monthly_active_users_bar = display_total_unique_active_users_by_month_bar_chart(monthly_active_users_data)
        if fig_monthly_active_users_bar:
            st.pyplot(fig_monthly_active_users_bar)
        else:
            pass # Info message handled in display function


    # Row 1: Monthly Reward Claims Trend (line chart) and Top 5 Most Claimed Rewards (bar chart)
    st.markdown("---")
    st.header("Reward Performance")
    col_trend, col_top_rewards = st.columns(2)

    with col_trend:
        st.subheader("Monthly Reward Claims Trend")
        with st.spinner(f"Generating chart..."):
            fig_monthly_claims = display_monthly_claims_trend_line_chart(claimed_rewards_df, logged_in_restaurant_name)
            if fig_monthly_claims:
                st.pyplot(fig_monthly_claims)
            else:
                st.info(f"No monthly claims data available to display for {logged_in_restaurant_name}.")

    with col_top_rewards:
        st.subheader("Top 5 Most Claimed Rewards")
        with st.spinner(f"Generating plot..."):
            fig_most_claimed = display_most_claimed_rewards(claimed_rewards_with_desc_df)
            if fig_most_claimed:
                st.pyplot(fig_most_claimed)
            else:
                pass # Info message handled in display function

    # Row 2: Daily Unique Active Users (line chart) and Customer Retention Rate (bar/gauge)
    st.markdown("---")
    st.header("User Activity & Retention")
    col_daily_active, col_retention = st.columns(2)

    with col_daily_active:
        st.subheader("Daily Unique Active Users")
        with st.spinner(f"Generating plot..."):
            fig_daily_active = display_daily_unique_active_users(profile_stamp_analytics_df, claimed_rewards_df)
            if fig_daily_active:
                st.pyplot(fig_daily_active)
            else:
                pass # Info message handled in display function

    with col_retention:
        st.subheader("Customer Retention Rate")
        with st.spinner(f"Generating plot..."):
            fig_retention = display_customer_retention_rate(profile_stamp_analytics_df)
            if fig_retention:
                st.pyplot(fig_retention)
            else:
                pass # Info message handled in display function

    # Row 3: Active vs Inactive Loyalty Members (donut/numbers)
    st.markdown("---")
    st.subheader("Active vs Inactive Loyalty Members")
    with st.spinner(f"Generating plot..."):
        fig_active_inactive = display_active_vs_inactive_members(profile_stamp_analytics_df, claimed_rewards_df)
        if fig_active_inactive:
            st.pyplot(fig_active_inactive)
        else:
            pass # Info message handled in display function
