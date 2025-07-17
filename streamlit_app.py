import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import os

# --- Config ---
# PLOTS_DIR is not strictly necessary for Streamlit as we display images directly,
# but keeping it for consistency if you still want to save plots locally.
PLOTS_DIR = 'public/images/analytics_plots'
os.makedirs(PLOTS_DIR, exist_ok=True)

# Database connection details
# Database connection details
PG_HOST = os.environ.get("PG_HOST")
PG_PORT = int(os.environ.get("PG_PORT", 6543)) # Convert to int, provide default
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

@st.cache_data(ttl=3600) # Cache data for 1 hour
def get_data_as_dataframe(query):
  """Fetches data from PostgreSQL and returns it as a pandas DataFrame."""
  conn = None
  try:
    conn = get_pg_connection()
    if conn:
      df = pd.read_sql_query(query, conn)
      return df
    return pd.DataFrame()
  except Exception as e:
    st.error(f"Error fetching data: {e}")
    return pd.DataFrame()
  finally:
    if conn:
      conn.close()

# --- Plotting Function (Modified for st.line_chart) ---
def prepare_monthly_claims_data(df: pd.DataFrame, restaurant_name: str):
    """
    Prepares monthly reward claims data for a specific restaurant to be used with st.line_chart.

    Args:
        df (pd.DataFrame): The input DataFrame containing reward claims data.
                           Must include 'claimed_at' (renamed to 'created_at' internally) and 'restaurant_name' columns.
        restaurant_name (str): The name of the restaurant for which to prepare the data.

    Returns:
        pd.Series: A Series with month_year as index and number of claims as values,
                   or None if no data found for the restaurant.
    """
    if df.empty:
        st.warning("No data to prepare for monthly reward claims trend.")
        return None

    # Ensure 'created_at' column exists for consistency
    if 'claimed_at' in df.columns and 'created_at' not in df.columns:
        df.rename(columns={'claimed_at': 'created_at'}, inplace=True)

    # Filter the DataFrame for the specified restaurant
    restaurant_df = df[df['restaurant_name'] == restaurant_name].copy()

    if restaurant_df.empty:
        st.warning(f"No data found for restaurant: {restaurant_name}")
        return None

    restaurant_df['created_at'] = pd.to_datetime(restaurant_df['created_at'], utc=True)
    restaurant_df['month_year'] = restaurant_df['created_at'].dt.to_period('M')

    # Group by month-year and count claims for the current restaurant
    monthly_claims = restaurant_df['month_year'].value_counts().sort_index()
    
    # Convert PeriodIndex to string for better display on x-axis in st.line_chart if needed
    # Although st.line_chart can often handle PeriodIndex, explicit string conversion can prevent issues.
    monthly_claims.index = monthly_claims.index.astype(str)
    
    # Rename the Series for clarity in the chart legend
    monthly_claims.name = 'Number of Claims'

    return monthly_claims

# --- Streamlit App Layout ---
st.set_page_config(layout="wide")
st.title("Restaurant Reward Claims Analytics")

# SQL query to fetch claimed rewards with restaurant names
query = """
SELECT
    csr.claimed_at,
    r.name AS restaurant_name
FROM
    public.claimed_stamp_rewards csr
JOIN
    public.restaurants r ON csr.restaurant_id = r.id
ORDER BY
    csr.claimed_at;
"""

# Fetch data
with st.spinner("Fetching data from the database..."):
    claimed_rewards_df = get_data_as_dataframe(query)

if claimed_rewards_df.empty:
    st.error("Could not retrieve data from the database. Please check your connection and credentials.")
else:
    st.success("Data fetched successfully!")
    
    # Get unique restaurant names for the dropdown
    unique_restaurants = sorted(claimed_rewards_df['restaurant_name'].unique())

    # Create a select box for restaurant selection
    selected_restaurant = st.selectbox(
        "Select a Restaurant:",
        unique_restaurants,
        index=0 # Default to the first restaurant in the list
    )

    if selected_restaurant:
        st.subheader(f"Monthly Reward Claims Trend for {selected_restaurant}")
        with st.spinner(f"Preparing data and generating chart for {selected_restaurant}..."):
            monthly_claims_data = prepare_monthly_claims_data(claimed_rewards_df, selected_restaurant)
            
            if monthly_claims_data is not None and not monthly_claims_data.empty:
                # st.line_chart directly takes the Series or DataFrame
                st.line_chart(monthly_claims_data)
            else:
                st.info(f"No monthly claims data available to display for {selected_restaurant}.")
    else:
        st.info("Please select a restaurant to view its analytics.")
