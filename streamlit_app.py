import streamlit as st

from app.auth.session import is_admin, is_authenticated
from app.database.db import init_db
from app.pages.analytics import render_analytics_page
from app.pages.auth import render_auth_page
from app.pages.chat import render_chat_page
from app.pages.dialogs import render_dialogs_page
from app.pages.knowledge_base import render_knowledge_base_page
from app.pages.rag_debug import render_rag_debug_page

st.set_page_config(page_title="AI Tutor", page_icon="🎓", layout="wide")

init_db()

if not is_authenticated():
    render_auth_page()
    st.stop()

USER_PAGES = ["Чат", "Мои диалоги"]
ADMIN_PAGES = ["База знаний", "RAG Debug", "Аналитика"]

if "active_page" not in st.session_state:
    st.session_state.active_page = "Чат"

available_pages = USER_PAGES + (ADMIN_PAGES if is_admin() else [])

if st.session_state.active_page not in available_pages:
    st.session_state.active_page = "Чат"

with st.sidebar:
    st.title("Навигация")
    page = st.radio(
        "Раздел",
        options=available_pages,
        index=available_pages.index(st.session_state.active_page),
        label_visibility="collapsed",
    )
    st.session_state.active_page = page

    if is_admin():
        st.caption("Режим администратора")

page = st.session_state.active_page

if page == "Чат":
    render_chat_page()
elif page == "Мои диалоги":
    render_dialogs_page()
elif page == "База знаний":
    render_knowledge_base_page()
elif page == "RAG Debug":
    render_rag_debug_page()
elif page == "Аналитика":
    render_analytics_page()
