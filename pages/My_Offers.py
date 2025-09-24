# pages/My_Offers2.py

import streamlit as st
from utils.auth import require_auth
from utils.offers import (
    render_offer_form, submit_offer,
    render_active_offers, render_pending_offers, render_admin_instructions
)
from utils.google_sheets import sync_offers_with_db
from utils.ui import show_db_error

st.set_page_config(layout="wide")

# Require authentication and get user/restaurant info
auth_info = require_auth()

st.title("Manager your Offers")

# Sync offers on page load
try:
    sync_offers_with_db(auth_info["restaurant_id"], auth_info["restaurant_name"])
except Exception as e:
    # If tables aren't created in this env, or any DB hiccup, show friendly error and continue
    show_db_error(e, context="Initial sync")

# Initialize session state
if "local_pending_offers" not in st.session_state:
    st.session_state.local_pending_offers = []

# Initialize offer submission success flag
if "offer_submitted" not in st.session_state:
    st.session_state.offer_submitted = False

# Show success message if offer was just submitted
if st.session_state.offer_submitted:
    st.success("Offer submitted for review! It will appear as 'pending' until approved.")
    st.session_state.offer_submitted = False

# Offer Creation Flow
# Offer Creation Flow (fixed)
st.subheader("Create a new offer")

# Persist the selected type across reruns
offer_type = st.selectbox(
    "Select Offer type from the drop down",
    ["Buy One Get One", "Percent Discount", "Special", "Surprise Bag"],
    index=None,
    key="offer_type_select"
)

if offer_type:
    offer_data = render_offer_form(offer_type)  # this is a form internally
    if offer_data:
        if submit_offer(auth_info["restaurant_id"], auth_info["restaurant_name"], offer_data):
            st.session_state.offer_submitted = True
            st.rerun()

# Display Offers
st.header("Your Offers")

# Active offers
render_active_offers(auth_info["restaurant_id"])

# Pending offers
render_pending_offers(auth_info["restaurant_id"])

# # Manual refresh button
# if st.button("Refresh Offers"):
#     sync_offers_with_db(auth_info["restaurant_id"], auth_info["restaurant_name"])
#     st.rerun()

# # Temporary test button
# if st.button("Test Google Sheets Connection"):
#     from utils.google_sheets import add_offer_to_sheet
#     test_offer = {
#         "offer_type": "Percent Discount",
#         "about": {
#             "en": {
#                 "title": "Debug Test Offer",
#                 "description": "Test description", 
#                 "summary": "Test summary"
#             }
#         },
#         "valid_days_of_week": None,
#         "valid_start_time": None,
#         "valid_end_time": None,
#         "start_date": "2025-09-24",
#         "end_date": None,
#         "unique_usage_per_user": False,
#     }
    
#     if add_offer_to_sheet(auth_info["restaurant_id"], auth_info["restaurant_name"], test_offer):
#         st.success("Test offer added to Google Sheets!")
#     else:
#         st.error("Test offer failed to add to Google Sheets!")

# # Admin instructions
# render_admin_instructions()