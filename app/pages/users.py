"""Admin user management page."""

from __future__ import annotations

import streamlit as st

from app.auth.session import get_current_user, is_admin, set_current_user
from app.services.user_admin_service import UserAdminError, UserAdminService


def _format_activity(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ")[:19]


def render_users_page() -> None:
    if not is_admin():
        st.error("Доступ только для администратора.")
        return

    service = UserAdminService()
    current_user = get_current_user()

    st.title("Пользователи")
    st.caption("Просмотр, создание, смена роли, сброс пароля и удаление учётных записей.")

    if message := st.session_state.pop("users_page_message", None):
        st.success(message)

    users = service.list_users()
    admin_count = sum(1 for user in users if user.role == "admin")

    col1, col2, col3 = st.columns(3)
    col1.metric("Всего пользователей", len(users))
    col2.metric("Администраторов", admin_count)
    col3.metric("Студентов", len(users) - admin_count)

    if users:
        st.dataframe(
            [
                {
                    "ID": user.id,
                    "Email": user.email,
                    "Роль": user.role,
                    "Уровень": user.current_level,
                    "Диалогов": user.session_count,
                    "Последняя активность": _format_activity(user.last_activity),
                    "Зарегистрирован": _format_activity(user.created_at),
                }
                for user in users
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Пользователей пока нет.")

    st.divider()
    st.subheader("Создать пользователя")
    with st.form("create_user_form"):
        new_email = st.text_input("Email")
        new_password = st.text_input("Пароль", type="password")
        new_role = st.selectbox("Роль", options=["user", "admin"], format_func=lambda r: r)
        create_submitted = st.form_submit_button("Создать", use_container_width=True)

    if create_submitted:
        try:
            result = service.create_user(new_email, new_password, role=new_role)
            st.session_state["users_page_message"] = (
                f"Пользователь {result.user.email} создан (роль: {result.user.role})."
            )
            st.rerun()
        except UserAdminError as exc:
            st.error(str(exc))

    if not users:
        return

    st.divider()
    st.subheader("Управление пользователем")
    user_options = {f"{user.email} ({user.role})": user for user in users}
    selected_label = st.selectbox("Выберите пользователя", options=list(user_options))
    selected = user_options[selected_label]

    st.markdown(
        f"**ID:** {selected.id}  \n"
        f"**Уровень:** {selected.current_level}  \n"
        f"**Диалогов:** {selected.session_count}  \n"
        f"**Последняя активность:** {_format_activity(selected.last_activity)}"
    )

    role_labels = {"user": "user (студент)", "admin": "admin (администратор)"}
    with st.form("change_role_form"):
        st.markdown("#### Смена роли")
        new_role = st.selectbox(
            "Роль",
            options=["user", "admin"],
            index=0 if selected.role == "user" else 1,
            format_func=lambda value: role_labels[value],
            key=f"role_select_{selected.id}",
        )
        role_submitted = st.form_submit_button("Сохранить роль", use_container_width=True)

    if role_submitted:
        try:
            updated = service.change_role(selected.id, new_role)
            if current_user and updated.id == current_user.id:
                set_current_user(updated)
            st.session_state["users_page_message"] = (
                f"Роль пользователя {updated.email} изменена на {updated.role}."
            )
            st.rerun()
        except UserAdminError as exc:
            st.error(str(exc))

    with st.form("reset_password_form"):
        st.markdown("#### Сброс пароля")
        reset_password = st.text_input("Новый пароль", type="password", key="reset_password")
        reset_confirm = st.text_input(
            "Подтвердите пароль",
            type="password",
            key="reset_password_confirm",
        )
        reset_submitted = st.form_submit_button("Сбросить пароль", use_container_width=True)

    if reset_submitted:
        if reset_password != reset_confirm:
            st.error("Пароли не совпадают.")
        else:
            try:
                service.reset_password(selected.id, reset_password)
                st.session_state["users_page_message"] = (
                    f"Пароль пользователя {selected.email} обновлён."
                )
                st.rerun()
            except UserAdminError as exc:
                st.error(str(exc))

    st.markdown("#### Удаление")
    if current_user and selected.id == current_user.id:
        st.warning("Нельзя удалить свою учётную запись из этой панели.")
    else:
        confirm_delete = st.checkbox(
            f"Подтверждаю удаление пользователя {selected.email}",
            key=f"confirm_delete_{selected.id}",
        )
        if st.button("Удалить пользователя", type="primary", disabled=not confirm_delete):
            try:
                service.delete_user(selected.id)
                st.session_state["users_page_message"] = (
                    f"Пользователь {selected.email} удалён."
                )
                st.rerun()
            except UserAdminError as exc:
                st.error(str(exc))
