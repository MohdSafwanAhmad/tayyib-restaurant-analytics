import streamlit as st

pg = st.navigation([st.Page("pages/analytics.py"), st.Page("pages/offers.py")])
pg.run()
