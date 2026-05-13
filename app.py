# app.py
import streamlit as st

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        st.switch_page("pages/01_login.py")
    else:
        st.switch_page("pages/02_warehouse.py")
except Exception:
    st.switch_page("pages/01_login.py")
