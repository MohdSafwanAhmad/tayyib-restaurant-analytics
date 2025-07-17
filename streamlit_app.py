import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import os
import streamlit_authenticator as st_auth
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# --- Config ---
PLOTS_DIR = 'public/images/analytics_plots'
os.makedirs(PLOTS_DIR, exist_ok=True)

# Set matplotlib style for consistent, clean plots
plt.style.use('default')
sns.set_palette("husl")

# Database connection details (fetched from environment variables)
PG_HOST = os.environ.get("PG_HOST")
PG_PORT = int(os.environ.get("PG_PORT", 6543))
PG_DBNAME = os.environ.get("PG_DBNAME")
PG_USER = os.environ.get("PG_USER")
PG_PASSWORD = os.environ.get("PG_PASSWORD")

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

@st.cache_data(ttl=3600)
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
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# --- Data Preparation and Display Functions ---

def prepare_monthly_claims_data(df: pd.DataFrame, restaurant_name: str):
    """
    Prepares monthly reward claims data for a specific restaurant to be used with st.line_chart.
    """
    if df.empty:
        return None

    restaurant_df = df[df['restaurant_name'].str.lower() == restaurant_name.lower()].copy()

    if restaurant_df.empty:
        st.info(f"No claims data found for your restaurant: {restaurant_name}. Or your restaurant name does not match our records.")
        return None

    restaurant_df['created_at'] = pd.to_datetime(restaurant_df['created_at'], utc=True)
    restaurant_df['month_year'] = restaurant_df['created_at'].dt.to_period('M')

    monthly_claims = restaurant_df['month_year'].value_counts().sort_index()
    monthly_claims.index = monthly_claims.index.astype(str)
    monthly_claims.name = 'Number of Claims'

    return monthly_claims

def display_most_claimed_rewards(df_claimed_rewards_with_desc: pd.DataFrame, restaurant_name: str):
    """Bar chart of the top 5 most claimed rewards for a specific restaurant."""
    if df_claimed_rewards_with_desc.empty:
        st.info(f"No data to plot for most claimed rewards for {restaurant_name}.")
        return None

    # Extract English summary
    df_claimed_rewards_with_desc['reward_summary'] = df_claimed_rewards_with_desc['description'].apply(
        lambda x: x['en']['summary'] if pd.notna(x) and isinstance(x, dict) and 'en' in x and 'summary' in x['en'] else 'Unknown'
    )

    # Count occurrences of each reward summary
    reward_counts = df_claimed_rewards_with_desc['reward_summary'].value_counts().head(5)

    if reward_counts.empty:
        st.info(f"No claimed rewards data available to determine top rewards for {restaurant_name}.")
        return None

    # Create smaller figure with better proportions
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(reward_counts.index, reward_counts.values, color='#4CAF50', alpha=0.8)
    
    # Add value labels on bars
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
                f'{int(width)}', ha='left', va='center', fontsize=10)
    
    ax.set_title('Top 5 Most Claimed Rewards', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Number of Claims', fontsize=12)
    ax.set_ylabel('Reward Summary', fontsize=12)
    
    # Improve layout
    ax.grid(axis='x', alpha=0.3)
    ax.set_axisbelow(True)
    plt.tight_layout()
    
    return fig

def display_daily_unique_active_users(df_profile_stamp_analytics: pd.DataFrame, df_claimed_stamp_rewards: pd.DataFrame, restaurant_name: str):
    """
    Line chart of daily unique active users for a specific restaurant.
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
        st.info(f"No combined activity data available for daily unique active users for {restaurant_name}.")
        return None

    all_activity['activity_time'] = pd.to_datetime(all_activity['activity_time'], utc=True)
    all_activity['activity_date'] = all_activity['activity_time'].dt.date

    daily_active_users = all_activity.groupby('activity_date')['profile_id'].nunique().reset_index()
    daily_active_users.columns = ['date', 'unique_users']
    daily_active_users['date'] = pd.to_datetime(daily_active_users['date'])
    daily_active_users.sort_values('date', inplace=True)

    if daily_active_users.empty:
        st.info(f"No daily active users data to plot for {restaurant_name}.")
        return None

    # Create smaller figure
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(daily_active_users['date'], daily_active_users['unique_users'], 
            marker='o', linewidth=2, markersize=4, color='#2196F3', alpha=0.8)
    
    ax.set_title('Daily Unique Active Users', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Number of Unique Users', fontsize=12)
    
    # Improve formatting
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return fig

def display_customer_retention_rate(df_profile_stamp_analytics: pd.DataFrame, restaurant_name: str, retention_days=30):
    """
    Calculate and visualize basic customer retention rate for a specific restaurant.
    """
    if df_profile_stamp_analytics.empty:
        st.info(f"No stamp analytics data to plot for customer retention rate for {restaurant_name}.")
        return None

    df_profile_stamp_analytics['created_at'] = pd.to_datetime(df_profile_stamp_analytics['created_at'], utc=True)

    # Get first scan date for each customer
    first_scans = df_profile_stamp_analytics.groupby('profile_id')['created_at'].min().reset_index()
    first_scans.columns = ['profile_id', 'first_scan_date']

    # Get all scan dates for each customer
    all_scans = df_profile_stamp_analytics.groupby('profile_id')['created_at'].apply(list).reset_index()
    all_scans.columns = ['profile_id', 'scan_dates']

    # Merge first scans with all scans
    customer_data = pd.merge(first_scans, all_scans, on='profile_id')

    # Calculate retention for different periods
    retention_periods = [30, 60, 90]
    retention_rates = []

    for days in retention_periods:
        retained_customers = 0
        total_customers = len(customer_data)

        for _, row in customer_data.iterrows():
            first_scan = row['first_scan_date']
            scan_dates = row['scan_dates']

            # Check if customer has scans after first scan within retention period
            retention_window = first_scan + pd.Timedelta(days=days)
            future_scans = [date for date in scan_dates if date > first_scan and date <= retention_window]

            if future_scans:
                retained_customers += 1

        retention_rate = (retained_customers / total_customers * 100) if total_customers > 0 else 0
        retention_rates.append(retention_rate)

    if not retention_rates:
        st.info(f"Not enough data to calculate retention rates for {restaurant_name}.")
        return None

    # Create smaller visualization with better layout
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Bar chart showing retention rates for different periods
    colors = ['#FF9800', '#2196F3', '#4CAF50']
    bars = ax1.bar([f'{days} Days' for days in retention_periods], retention_rates, color=colors, alpha=0.8)
    ax1.set_title('Customer Retention Rate by Period', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Retention Rate (%)', fontsize=12)
    ax1.set_ylim(0, 100)
    ax1.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bar, rate in zip(bars, retention_rates):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold', fontsize=10)

    # Gauge-style visualization for 30-day retention
    retention_30 = retention_rates[0]

    # Create a semi-circular gauge
    theta = np.linspace(0, np.pi, 100)
    radius = 1

    # Background arc
    ax2.plot(radius * np.cos(theta), radius * np.sin(theta), '#E0E0E0', linewidth=15)

    # Retention arc
    retention_theta = np.linspace(0, np.pi * (retention_30 / 100), max(2, int(retention_30)))
    if len(retention_theta) > 0:
        ax2.plot(radius * np.cos(retention_theta), radius * np.sin(retention_theta),
                colors[0], linewidth=15)

    # Add text in center
    ax2.text(0, 0.2, f'{retention_30:.1f}%', ha='center', va='center',
             fontsize=20, fontweight='bold', color=colors[0])
    ax2.text(0, -0.1, '30-Day Retention', ha='center', va='center',
             fontsize=12, color='gray')

    ax2.set_xlim(-1.2, 1.2)
    ax2.set_ylim(-0.2, 1.2)
    ax2.set_aspect('equal')
    ax2.axis('off')
    ax2.set_title('30-Day Customer Retention Rate', fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    return fig

def display_active_vs_inactive_members(df_profile_stamp_analytics: pd.DataFrame, df_claimed_stamp_rewards: pd.DataFrame, restaurant_name: str, activity_days=30):
    """
    Visualize active vs inactive loyalty members for a specific restaurant.
    """
    all_members = set()
    active_members = set()

    # Get current date and activity cutoff
    current_date = pd.Timestamp.now(tz='UTC')
    activity_cutoff = current_date - pd.Timedelta(days=activity_days)

    # Process stamp scan activity
    if not df_profile_stamp_analytics.empty:
        df_profile_stamp_analytics['created_at'] = pd.to_datetime(df_profile_stamp_analytics['created_at'], utc=True)
        all_members.update(df_profile_stamp_analytics['profile_id'].unique())

        recent_scanners = df_profile_stamp_analytics[
            df_profile_stamp_analytics['created_at'] >= activity_cutoff
        ]['profile_id'].unique()
        active_members.update(recent_scanners)

    # Process reward claim activity
    if not df_claimed_stamp_rewards.empty:
        df_claimed_stamp_rewards['created_at'] = pd.to_datetime(df_claimed_stamp_rewards['created_at'], utc=True)
        all_members.update(df_claimed_stamp_rewards['profile_id'].unique())

        recent_claimers = df_claimed_stamp_rewards[
            df_claimed_stamp_rewards['created_at'] >= activity_cutoff
        ]['profile_id'].unique()
        active_members.update(recent_claimers)

    # Calculate counts
    total_members = len(all_members)
    active_count = len(active_members)
    inactive_count = total_members - active_count

    if total_members == 0:
        st.info(f"No member activity data to plot for active vs inactive members for {restaurant_name}.")
        return None

    # Calculate percentages
    active_percentage = (active_count / total_members * 100)
    inactive_percentage = (inactive_count / total_members * 100)

    # Create smaller visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Donut chart
    sizes = [active_count, inactive_count]
    labels = ['Active', 'Inactive']
    colors = ['#4CAF50', '#FF5722']
    explode = (0.05, 0)

    wedges, texts, autotexts = ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                       startangle=90, explode=explode, pctdistance=0.85,
                                       wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2))

    # Improve text formatting
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)

    # Add center text
    ax1.text(0, 0, f'{total_members}\nTotal\nMembers', ha='center', va='center',
             fontsize=12, fontweight='bold', color='gray')

    ax1.set_title(f'Active vs Inactive Members\n(Last {activity_days} Days)', fontsize=14, fontweight='bold')

    # Statistics display
    ax2.text(0.25, 0.7, f'{active_count}', ha='center', va='center',
             fontsize=36, fontweight='bold', color=colors[0])
    ax2.text(0.25, 0.55, 'ACTIVE', ha='center', va='center',
             fontsize=14, fontweight='bold', color=colors[0])
    ax2.text(0.25, 0.45, f'{active_percentage:.1f}%', ha='center', va='center',
             fontsize=14, color=colors[0])

    ax2.text(0.75, 0.7, f'{inactive_count}', ha='center', va='center',
             fontsize=36, fontweight='bold', color=colors[1])
    ax2.text(0.75, 0.55, 'INACTIVE', ha='center', va='center',
             fontsize=14, fontweight='bold', color=colors[1])
    ax2.text(0.75, 0.45, f'{inactive_percentage:.1f}%', ha='center', va='center',
             fontsize=14, color=colors[1])

    # Add divider line
    ax2.axvline(x=0.5, color='lightgray', linestyle='--', alpha=0.7)

    ax2.text(0.5, 0.2, f'Total Members: {total_members}', ha='center', va='center',
             fontsize=12, fontweight='bold', color='gray')
    ax2.text(0.5, 0.1, f'Activity Period: Last {activity_days} Days', ha='center', va='center',
             fontsize=10, color='gray')

    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.set_aspect('equal')
    ax2.axis('off')
    ax2.set_title('Member Activity Breakdown', fontsize=14, fontweight='bold')

    plt.tight_layout()
    return fig

# --- Streamlit App Layout ---
st.set_page_config(layout="wide", page_title="Tayyib App Dashboard")

# Custom CSS for better styling
st.markdown("""
<style>
    .plot-container {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin: 5px 0;
    }
    .main-title {
        color: #2c3e50;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .section-title {
        color: #34495e;
        font-size: 1.5rem;
        font-weight: 600;
        margin: 1.5rem 0 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION SETUP ---
names = ["Baan Lao", "Crusty's NDG", "Mama Khan"]
usernames = ["Baan Lao", "Crusty's NDG", "Mama Khan"]
hashed_passwords = [
    st_auth.Hasher(['passwordA1']).generate()[0],
    st_auth.Hasher(['passwordB2']).generate()[0],
    st_auth.Hasher(['passwordC3']).generate()[0]
]

credentials = {
    "usernames": {
        usernames[0]: {"email": "baan.lao@example.com", "name": names[0], "password": hashed_passwords[0]},
        usernames[1]: {"email": "crustys.ndg@example.com", "name": names[1], "password": hashed_passwords[1]},
        usernames[2]: {"email": "mama.khan@example.com", "name": names[2], "password": hashed_passwords[2]},
    }
}

authenticator = st_auth.Authenticate(
    credentials,
    "streamlit_app_cookie",
    "abcdef",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login("Login", "main")

# --- Conditional Display based on Authentication Status ---
if authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
elif authentication_status:
    # User is logged in
    st.sidebar.title(f"Welcome {name}")
    authenticator.logout("Logout", "sidebar")

    # Main title with custom styling
    st.markdown(f'<h1 class="main-title">📊 Tayyib App Dashboard: {name}</h1>', unsafe_allow_html=True)
    
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
        st.stop()

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

    logged_in_restaurant_name = username

    # --- Display Plots in Grid Layout ---
    
    # Row 1: Monthly Claims and Most Claimed Rewards
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="plot-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="section-title">📈 Monthly Reward Claims Trend</h3>', unsafe_allow_html=True)
        with st.spinner("Loading monthly claims data..."):
            monthly_claims_data = prepare_monthly_claims_data(claimed_rewards_df, logged_in_restaurant_name)
            if monthly_claims_data is not None and not monthly_claims_data.empty:
                st.line_chart(monthly_claims_data, height=300)
            else:
                st.info("No monthly claims data available.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="plot-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="section-title">🏆 Top 5 Most Claimed Rewards</h3>', unsafe_allow_html=True)
        with st.spinner("Loading most claimed rewards..."):
            fig_most_claimed = display_most_claimed_rewards(claimed_rewards_with_desc_df, logged_in_restaurant_name)
            if fig_most_claimed:
                st.pyplot(fig_most_claimed, use_container_width=True)
            else:
                st.info("No rewards data available.")
        st.markdown('</div>', unsafe_allow_html=True)

    # Row 2: Daily Active Users and Retention Rate
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown('<div class="plot-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="section-title">👥 Daily Unique Active Users</h3>', unsafe_allow_html=True)
        with st.spinner("Loading daily active users..."):
            fig_daily_active = display_daily_unique_active_users(profile_stamp_analytics_df, claimed_rewards_df, logged_in_restaurant_name)
            if fig_daily_active:
                st.pyplot(fig_daily_active, use_container_width=True)
            else:
                st.info("No daily active users data available.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="plot-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="section-title">🔄 Customer Retention Rate</h3>', unsafe_allow_html=True)
        with st.spinner("Loading retention data..."):
            fig_retention = display_customer_retention_rate(profile_stamp_analytics_df, logged_in_restaurant_name)
            if fig_retention:
                st.pyplot(fig_retention, use_container_width=True)
            else:
                st.info("No retention data available.")
        st.markdown('</div>', unsafe_allow_html=True)

    # Row 3: Active vs Inactive Members (full width)
    st.markdown('<div class="plot-container">', unsafe_allow_html=True)
    st.markdown('<h3 class="section-title">⚡ Active vs Inactive Loyalty Members</h3>', unsafe_allow_html=True)
    with st.spinner("Loading member activity data..."):
        fig_active_inactive = display_active_vs_inactive_members(profile_stamp_analytics_df, claimed_rewards_df, logged_in_restaurant_name)
        if fig_active_inactive:
            st.pyplot(fig_active_inactive, use_container_width=True)
        else:
            st.info("No member activity data available.")
    st.markdown('</div>', unsafe_allow_html=True)