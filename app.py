"""Yelp project — Streamlit entry point.

Run:  python -m streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Who Leaves Yelp Reviews?", layout="wide")

page = st.navigation([
    st.Page("views/reviews_map.py", title="Reviews vs. population", icon=":material/map:", default=True),
    st.Page("views/review_length.py", title="What's in a review?", icon=":material/rate_review:"),
])
page.run()
