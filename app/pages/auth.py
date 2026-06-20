"""Authentication UI for Streamlit."""

from __future__ import annotations

import streamlit as st

from app.auth.service import AuthError, AuthService
from app.auth.session import set_current_user
from app.database.db import init_db


def render_auth_page() -> None:
    init_db()
    st.title("ИИ-куратор образовательной платформы")
    st.caption("Вход или регистрация обязательны. Гостевой доступ запрещён.")

    auth = AuthService()
    tab_login, tab_register = st.tabs(["Вход", "Регистрация"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Пароль", type="password", key="login_password")
            submitted = st.form_submit_button("Войти", use_container_width=True)

        if submitted:
            try:
                result = auth.login(email, password)
                set_current_user(result.user)
                st.session_state.active_page = "Чат"
                st.success(f"Добро пожаловать, {result.user.email}!")
                st.rerun()
            except AuthError as exc:
                st.error(str(exc))

    with tab_register:
        with st.form("register_form"):
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Пароль", type="password", key="register_password")
            password_confirm = st.text_input(
                "Подтвердите пароль",
                type="password",
                key="register_password_confirm",
            )
            submitted = st.form_submit_button("Зарегистрироваться", use_container_width=True)

        if submitted:
            if password != password_confirm:
                st.error("Пароли не совпадают.")
            else:
                try:
                    result = auth.register(email, password)
                    set_current_user(result.user)
                    st.session_state.active_page = "Чат"
                    st.success("Регистрация успешна!")
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
