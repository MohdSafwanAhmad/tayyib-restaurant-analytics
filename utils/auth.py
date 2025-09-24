# utils/auth.py
import streamlit as st
import streamlit_authenticator as st_auth
from utils.queries import get_restaurant_id_for_login

def get_admin_usernames():
    """Get list of admin usernames from secrets"""
    try:
        admins = list(st.secrets["auth"].get("admins", []))
        return admins if admins else ["admin"]
    except Exception:
        return ["admin"]

def load_auth_from_secrets():
    """Load authentication configuration from Streamlit secrets"""
    try:
        s = st.secrets["auth"]
        creds = {"usernames": {}}
        for uname, uinfo in s["credentials"]["usernames"].items():
            creds["usernames"][uname] = {
                "email": uinfo["email"],
                "name": uinfo["name"],
                "password": uinfo["password"],
            }
        cookie_conf = s["cookie"]
        preauth = s.get("preauthorized", {"emails": []})
        assert cookie_conf["name"] and cookie_conf["key"]
        return creds, cookie_conf, preauth
    except Exception as e:
        st.error(f"Auth configuration error: {e}")
        st.stop()

def authenticate_user():
    """Handle user authentication and return user info"""
    credentials, cookie_conf, preauthorized = load_auth_from_secrets()
    authenticator = st_auth.Authenticate(
        credentials, cookie_conf["name"], cookie_conf["key"], 
        cookie_conf["expiry_days"], preauthorized
    )
    
    name, authentication_status, username = authenticator.login("Login", "main")
    
    if authentication_status is False:
        st.error("Username/password is incorrect")
        st.stop()
    elif authentication_status is None:
        st.warning("Please enter your username and password")
        st.stop()
    
    # User is authenticated
    display_name = credentials["usernames"][username]["name"]
    st.sidebar.title(f"Welcome {display_name}")
    authenticator.logout("Logout", "sidebar")
    
    return {
        "username": username,
        "display_name": display_name,
        "is_admin": username in set(get_admin_usernames()),
        "authenticator": authenticator
    }

def get_restaurant_info(username):
    """Get restaurant ID and info for authenticated user"""
    rid_df = get_restaurant_id_for_login(username)
    if rid_df.empty:
        st.error(f"Could not find restaurant ID for {username}.")
        st.stop()
    
    return {
        "restaurant_id": rid_df.iloc[0]['id'],
        "restaurant_name": username  # or get from database if you have it
    }

def require_auth():
    """Decorator-style function to require authentication"""
    user_info = authenticate_user()
    restaurant_info = get_restaurant_info(user_info["username"])
    
    return {**user_info, **restaurant_info}