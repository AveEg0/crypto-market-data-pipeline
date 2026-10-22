import streamlit as st

st.set_page_config(page_title="Crypto Market Data", layout="wide")

pages = [
    st.Page("views/market.py", title="Market Data", default=True),
    st.Page("views/backtest.py", title="Backtest"),
]
st.navigation(pages).run()
