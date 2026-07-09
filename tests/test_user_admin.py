from __future__ import annotations

import pytest

from app.auth.service import AuthService
from app.database.db import init_db
from app.database.repository import UserRepository
from app.services.user_admin_service import UserAdminError, UserAdminService


@pytest.fixture
def admin_service(settings) -> UserAdminService:
    init_db(settings)
    users = UserRepository(settings)
    users.create_user("admin@example.com", "hash", role="admin")
    return UserAdminService(users, AuthService(users))


def test_list_users_includes_stats(admin_service: UserAdminService) -> None:
    admin_service.create_user("student@example.com", "password123", role="user")
    users = admin_service.list_users()
    assert len(users) == 2
    student = next(user for user in users if user.email == "student@example.com")
    assert student.role == "user"
    assert student.session_count == 0
    assert student.last_activity is None


def test_create_user_with_role(admin_service: UserAdminService) -> None:
    result = admin_service.create_user("new-admin@example.com", "password123", role="admin")
    assert result.user.role == "admin"


def test_reset_password(admin_service: UserAdminService) -> None:
    created = admin_service.create_user("student@example.com", "oldpass1", role="user")
    admin_service.reset_password(created.user.id, "newpass2")
    auth = AuthService(UserRepository(admin_service.users.settings))
    assert auth.login("student@example.com", "newpass2").user.id == created.user.id


def test_delete_user(admin_service: UserAdminService) -> None:
    created = admin_service.create_user("student@example.com", "password123", role="user")
    admin_service.delete_user(created.user.id)
    assert all(user.email != "student@example.com" for user in admin_service.list_users())


def test_cannot_delete_last_admin(admin_service: UserAdminService) -> None:
    users = admin_service.list_users()
    only_admin = next(user for user in users if user.role == "admin")
    with pytest.raises(UserAdminError, match="последнего администратора"):
        admin_service.delete_user(only_admin.id)


def test_change_role_promote_to_admin(admin_service: UserAdminService) -> None:
    created = admin_service.create_user("student@example.com", "password123", role="user")
    updated = admin_service.change_role(created.user.id, "admin")
    assert updated.role == "admin"


def test_cannot_demote_last_admin(admin_service: UserAdminService) -> None:
    users = admin_service.list_users()
    only_admin = next(user for user in users if user.role == "admin")
    with pytest.raises(UserAdminError, match="последнего администратора"):
        admin_service.change_role(only_admin.id, "user")


def test_change_role_when_two_admins(admin_service: UserAdminService) -> None:
    second = admin_service.create_user("admin2@example.com", "password123", role="admin")
    updated = admin_service.change_role(second.user.id, "user")
    assert updated.role == "user"
    assert admin_service.users.count_admins() == 1
