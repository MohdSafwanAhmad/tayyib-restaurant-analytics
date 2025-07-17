import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import os
import streamlit_authenticator as st_auth

# --- Config ---
PLOTS_DIR = 'public/images/analytics_plots'
os.makedirs(PLOTS_DIR, exist_ok=True)

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

# --- Data Preparation Function ---
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
        # st.warning("No data to prepare for monthly reward claims trend.") # Suppress for login screen
        return None

    # Ensure 'created_at' column exists for consistency
    if 'claimed_at' in df.columns and 'created_at' not in df.columns:
        df.rename(columns={'claimed_at': 'created_at'}, inplace=True)

    # --- IMPORTANT CHANGE: Make filtering case-insensitive ---
    # Convert both the DataFrame column and the input restaurant_name to lowercase for comparison
    restaurant_df = df[df['restaurant_name'].str.lower() == restaurant_name.lower()].copy()

    if restaurant_df.empty:
        st.info(f"No claims data found for your restaurant: {restaurant_name}. Or your restaurant name does not match our records.")
        return None

    restaurant_df['created_at'] = pd.to_datetime(restaurant_df['created_at'], utc=True)
    restaurant_df['month_year'] = restaurant_df['created_at'].dt.to_period('M')

    # Group by month-year and count claims for the current restaurant
    monthly_claims = restaurant_df['month_year'].value_counts().sort_index()
    monthly_claims.index = monthly_claims.index.astype(str)
    monthly_claims.name = 'Number of Claims'

    return monthly_claims

# --- Streamlit App Layout ---
st.set_page_config(layout="wide")

# --- AUTHENTICATION SETUP ---
# In a real app, you would fetch these from a secure database
# For demonstration, we'll hardcode some users.
# You MUST hash passwords for production!
# You can use `st_auth.Hasher(['your_password']).generate()` to get a hashed password.

# Example: Hasher(['password123']).generate() -> '$2b$12$...'
# We will use the *exact* restaurant names from your database as usernames here.
# Based on your schema, restaurant names are: "Mama Khan", "Crusty's NDG", "Baan Lao"
names = ["Baan Lao", "Crusty's NDG", "Mama Khan"] # Display names
usernames = ["Baan Lao", "Crusty's NDG", "Mama Khan"] # Usernames for login
hashed_passwords = [
    st_auth.Hasher(['passwordA1']).generate()[0], # Password for Baan Lao
    st_auth.Hasher(['passwordB2']).generate()[0], # Password for Crusty's NDG
    st_auth.Hasher(['passwordC3']).generate()[0]  # Password for Mama Khan
]

# Create a dictionary of credentials
credentials = {
    "usernames": {
        usernames[0]: {"email": "baan.lao@example.com", "name": names[0], "password": hashed_passwords[0]},
        usernames[1]: {"email": "crustys.ndg@example.com", "name": names[1], "password": hashed_passwords[1]},
        usernames[2]: {"email": "mama.khan@example.com", "name": names[2], "password": hashed_passwords[2]},
    }
}
# print(credentials) # Keep this commented for deployment, only for local debugging

authenticator = st_auth.Authenticate(
    credentials,
    "streamlit_app_cookie", # Cookie name
    "abcdef", # Key for hashing cookie
    cookie_expiry_days=30 # Days before cookie expires
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
    authenticator.logout("Logout", "sidebar") # Logout button in sidebar

    st.title("Restaurant Reward Claims Analytics")
    st.subheader(f"Dashboard for {name}")

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
        
        # --- Debugging Aid (Temporary) ---
        # Uncomment the line below to see the exact unique restaurant names from your DB
        # This helps confirm if there's a casing mismatch or missing data
        # st.write("Unique restaurant names from DB:", claimed_rewards_df['restaurant_name'].unique())
        
        # --- Display Data for the Logged-in Restaurant ---
        # The username from the authenticator is the restaurant_name in this setup
        logged_in_restaurant_name = username 

        st.subheader(f"Monthly Reward Claims Trend for {logged_in_restaurant_name}")
        with st.spinner(f"Preparing data and generating chart for {logged_in_restaurant_name}..."):
            monthly_claims_data = prepare_monthly_claims_data(claimed_rewards_df, logged_in_restaurant_name)
            
            if monthly_claims_data is not None and not monthly_claims_data.empty:
                st.line_chart(monthly_claims_data)
            else:
                st.info(f"No monthly claims data available to display for {logged_in_restaurant_name}.")
