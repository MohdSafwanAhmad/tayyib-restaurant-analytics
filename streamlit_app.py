import streamlit as st

pg = st.navigation([st.Page("pages/My_Dashboard.py"), st.Page("pages/My_Offers.py")])
pg.run()

