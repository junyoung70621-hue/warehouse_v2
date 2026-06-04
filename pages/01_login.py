# pages/01_login.py
import streamlit as st
from utils.notice import render_migration_notice

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="centered",
    initial_sidebar_state="collapsed"
)

render_migration_notice()
