# utils/offers.py
import streamlit as st
import pandas as pd
from datetime import time, date, datetime, timedelta
from utils.queries import get_existing_offers
from utils.google_sheets import add_offer_to_sheet, get_pending_offers_from_sheet, sync_offers_with_db
from utils.ui import show_success, show_error, show_info, render_status_badge, format_currency, show_db_error

# Constants
DAYS_MAPPING = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 0}
OFFER_TYPES = ["Buy One Get One", "Percent Discount", "Special", "Surprise Bag"]

def _safe(s):
    """Safely convert value to string, handling None and NaN"""
    return "" if pd.isna(s) or s is None else str(s)

def _parse_time(s: str | None) -> time:
    """Parse time string to time object"""
    if not s:
        return time(0, 0)
    try:
        hh, mm = s.split(":")
        return time(int(hh), int(mm))
    except Exception:
        return time(0, 0)

def format_days(days_array):
    """Convert days array to readable format"""
    if not days_array:
        return "All days"
    day_names = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
    return ", ".join([day_names[day] for day in days_array])

def render_offer_form(offer_type):
    """Render the detailed offer creation form"""
    with st.form(key="Add new offer details", clear_on_submit=True):
        st.subheader(offer_type)
        
        # Common fields
        offer_data = {}
        offer_data["title"] = st.text_input("Offer Title")
        offer_data["description"] = st.text_area("Offer Description")
        offer_data["summary"] = st.text_input("Offer Summary")
        
        # Surprise Bag specific fields
        if offer_type == "Surprise Bag":
            col1, col2 = st.columns(2)
            with col1:
                offer_data["price"] = st.number_input("Price ($)", min_value=0.01, step=0.01)
                offer_data["estimated_value"] = st.number_input("Estimated Value ($)", min_value=0.01, step=0.01)
            with col2:
                is_recurring = st.radio("Bag Type", ["Daily (recurring)", "One-time limited"])
                if is_recurring == "Daily (recurring)":
                    offer_data["daily_quantity"] = st.number_input("Daily Quantity", min_value=1, step=1)
                else:
                    offer_data["total_quantity"] = st.number_input("Total Quantity", min_value=1, step=1)
                offer_data["is_recurring"] = is_recurring
        
        # Scheduling
        st.subheader("Scheduling")
        offer_data["valid_days"] = st.multiselect(
            "Valid days of week (leave empty for all days)",
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        )
        
        col3, col4 = st.columns(2)
        with col3:
            offer_data["start_time"] = st.time_input("Daily start time", value=time(0, 0))
        with col4:
            offer_data["end_time"] = st.time_input("Daily end time", value=time(23, 59))
        
        # Validity period
        st.subheader("Validity Period")
        col5, col6 = st.columns(2)
        with col5:
            offer_data["start_date"] = st.date_input("Start Date", value=date.today())
        with col6:
            offer_data["end_date"] = st.date_input("End Date (optional)", value=None)
        
        # Usage limits
        offer_data["unique_usage"] = st.checkbox("Unique usage per user", value=False)
        
        # Submit
        add_clicked = st.form_submit_button("Add Offer", type="primary")
        
        if add_clicked:
            return process_offer_submission(offer_type, offer_data)
        
        return None

def process_offer_submission(offer_type, offer_data):
    """Process and validate offer submission"""
    if not offer_data["title"]:
        show_error("Offer title is required")
        return None
    
    # Prepare offer data for submission
    processed_data = {
        "offer_type": offer_type,
        "about": {
            "en": {
                "title": offer_data["title"],
                "description": offer_data["description"],
                "summary": offer_data["summary"]
            }
        },
        "valid_days_of_week": [DAYS_MAPPING[day] for day in offer_data["valid_days"]] if offer_data["valid_days"] else None,
        "valid_start_time": offer_data["start_time"] if offer_data["start_time"] != time(0, 0) else None,
        "valid_end_time": offer_data["end_time"] if offer_data["end_time"] != time(23, 59) else None,
        "start_date": offer_data["start_date"],
        "end_date": offer_data["end_date"],
        "unique_usage_per_user": offer_data["unique_usage"],
    }
    
    # Add surprise bag specific data
    if offer_type == "Surprise Bag":
        processed_data["surprise_bag"] = {
            "price": offer_data["price"],
            "estimated_value": offer_data["estimated_value"],
        }
        if offer_data["is_recurring"] == "Daily (recurring)":
            processed_data["surprise_bag"]["daily_quantity"] = offer_data["daily_quantity"]
        else:
            processed_data["surprise_bag"]["total_quantity"] = offer_data["total_quantity"]
    
    return processed_data

def submit_offer(restaurant_id, restaurant_name, offer_data):
    """Submit offer to Google Sheets"""
    
    try:
        # Call the Google Sheets function
        result = add_offer_to_sheet(restaurant_id, restaurant_name, offer_data)
        return result
    except Exception as e:
        st.error(f"Failed to submit offer: {e}")
        return False

def render_active_offers(restaurant_id):
    """Render active offers section"""
    st.subheader("Active Offers")
    try:
        with st.spinner("Loading active offers..."):
            df = get_existing_offers(restaurant_id)
    except Exception as e:
        show_db_error(e, context="Active Offers")
        show_info("No active offers found")
        return

    if df is None or df.empty:
        show_info("No active offers found")
        return

    for _, offer in df.iterrows():
        used_text = f"Used {offer.get('redemption_count', 0)} times"
        render_offer_card(offer, "🟢", used_text)


def render_pending_offers(restaurant_id):
    """Render pending offers section"""
    st.subheader("Pending Review")
    try:
        with st.spinner("Loading pending offers..."):
            pending_offers = get_pending_offers_from_sheet(restaurant_id)
    except Exception as e:
        show_error("Failed to load pending offers.")
        with st.expander("Technical details"):
            st.code(f"{type(e).__name__}: {e}")
        return

    if not pending_offers:
        show_info("No pending offers")
        return

    for i, offer in enumerate(pending_offers):
        title = offer["about"]["en"]["title"]
        render_pending_offer_card(offer, title)

def render_offer_card(offer, icon, subtitle):
    """Render an individual offer card"""
    about = offer['about'] if isinstance(offer['about'], dict) else {}
    title = about.get('en', {}).get('title', 'Untitled Offer')
    description = about.get('en', {}).get('description', 'No description')
    
    with st.expander(f"{icon} {title} - {subtitle}"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Type:** {offer['offer_type_name']}")
            st.write(f"**Description:** {description}")
            st.write(f"**Times Redeemed:** {int(offer['redemption_count'])}")
            st.write(f"**Valid Days:** {format_days(offer['valid_days_of_week'])}")
            
            if offer['valid_start_time']:
                st.write(f"**Daily Hours:** {offer['valid_start_time']} - {offer['valid_end_time'] or 'Open'}")
        
        with col2:
            st.write(f"**Start Date:** {offer['start_date']}")
            if offer['end_date']:
                st.write(f"**End Date:** {offer['end_date']}")
            
            # Surprise bag details
            if pd.notna(offer['price']):
                st.write(f"**Price:** {format_currency(offer['price'])}")
                st.write(f"**Estimated Value:** {format_currency(offer['estimated_value'])}")
                if pd.notna(offer['daily_quantity']):
                    st.write(f"**Daily Quantity:** {offer['daily_quantity']}")
                    st.write(f"**Current Daily Remaining:** {offer['current_daily_quantity'] or offer['daily_quantity']}")
                elif pd.notna(offer['total_quantity']):
                    st.write(f"**Total Quantity:** {offer['total_quantity']}")
                    remaining = offer['total_quantity'] - offer['redemption_count']
                    st.write(f"**Remaining:** {max(0, remaining)}")

def render_pending_offer_card(offer, title):
    """Render a pending offer card safely for all offer types."""
    with st.expander(f"🟡 {title} - Pending Review"):
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Type:** {offer.get('offer_type', 'Unknown')}")
            st.write(f"**Description:** {offer.get('about',{}).get('en',{}).get('description','')}")
            st.write(f"**Summary:** {offer.get('about',{}).get('en',{}).get('summary','')}")
            ts = offer.get("timestamp","")
            st.write(f"**Submitted:** {ts[:16] if isinstance(ts, str) else ts}")

        with col2:
            st.write(f"**Valid Days:** {format_days(offer.get('valid_days_of_week'))}")
            st.write(f"**Start Date:** {offer.get('start_date') or '—'}")
            if offer.get('end_date'):
                st.write(f"**End Date:** {offer.get('end_date')}")

            # Surprise bag details (guarded)
            if str(offer.get('offer_type')).lower() == "surprise bag":
                sb = offer.get("surprise_bag") or {}
                price = sb.get("price")
                est   = sb.get("estimated_value")
                if price is not None:
                    st.write(f"**Price:** {format_currency(price)}")
                if est is not None:
                    st.write(f"**Estimated Value:** {format_currency(est)}")
                if "daily_quantity" in sb:
                    dq = sb.get("daily_quantity")
                    if dq is not None:
                        st.write(f"**Daily Quantity:** {dq}")
                if "total_quantity" in sb:
                    tq = sb.get("total_quantity")
                    if tq is not None:
                        st.write(f"**Total Quantity:** {tq}")

        show_info("This offer is pending review and will be activated once approved by the admin.")


def render_admin_instructions():
    """Render admin instructions"""
    with st.expander("For Admins: Database Integration Instructions"):
        st.markdown("""
        ### Steps to approve pending offers:
        
        1. **Check Google Sheets** for pending offers
        2. **Insert into database** using SQL:
        
        ```sql
        -- For regular offers
        INSERT INTO offers (restaurant_id, about, offer_type, valid_days_of_week, 
                           valid_start_time, valid_end_time, start_date, end_date, 
                           unique_usage_per_user)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        
        -- For surprise bags, also insert:
        INSERT INTO surprise_bags (offer_id, price, estimated_value, daily_quantity, total_quantity)
        VALUES (%s, %s, %s, %s, %s);
        ```
        
        3. **Refresh the page** - approved offers will automatically move from pending to active
        
        ### Google Sheets Setup:
        - Sheet name: "Restaurant_Offers_Pending"
        - Columns: timestamp, restaurant_id, restaurant_name, offer_type, title, description, summary, valid_days_of_week, valid_start_time, valid_end_time, start_date, end_date, unique_usage_per_user, surprise_bag_data, status
        """)