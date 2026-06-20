from __future__ import annotations

import streamlit as st

from app.database.models import User


def is_authenticated() -> bool:
    return st.session_state.get("auth_user") is not None


def get_current_user() -> User | None:
    data = st.session_state.get("auth_user")
    if not data:
        return None
    return User(
        id=data["id"],
        email=data["email"],
        role=data["role"],
        created_at=data["created_at"],
    )


def set_current_user(user: User) -> None:
    st.session_state.auth_user = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
    }


def logout() -> None:
    for key in (
        "auth_user",
        "current_session_id",
        "chat_messages",
        "active_page",
    ):
        st.session_state.pop(key, None)


def is_admin() -> bool:
    user = get_current_user()
    return user is not None and user.role == "admin"
