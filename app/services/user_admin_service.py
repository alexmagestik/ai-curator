from __future__ import annotations

from dataclasses import dataclass

from app.auth.passwords import hash_password
from app.auth.service import AuthError, AuthService
from app.database.models import User, UserSummary
from app.database.repository import UserRepository


class UserAdminError(Exception):
    pass


@dataclass(frozen=True)
class CreateUserResult:
    user: User


class UserAdminService:
    def __init__(
        self,
        user_repository: UserRepository | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self.users = user_repository or UserRepository()
        self.auth = auth_service or AuthService(self.users)

    def list_users(self) -> list[UserSummary]:
        return self.users.list_users_with_stats()

    def create_user(self, email: str, password: str, role: str = "user") -> CreateUserResult:
        if role not in ("user", "admin"):
            raise UserAdminError("Роль должна быть user или admin.")
        try:
            result = self.auth.register(email, password, role=role)
        except AuthError as exc:
            raise UserAdminError(str(exc)) from exc
        return CreateUserResult(user=result.user)

    def reset_password(self, user_id: int, new_password: str) -> None:
        if len(new_password) < 6:
            raise UserAdminError("Пароль должен содержать минимум 6 символов.")
        if self.users.get_by_id(user_id) is None:
            raise UserAdminError("Пользователь не найден.")
        self.users.update_password(user_id, hash_password(new_password))

    def change_role(self, user_id: int, role: str) -> User:
        if role not in ("user", "admin"):
            raise UserAdminError("Роль должна быть user или admin.")
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserAdminError("Пользователь не найден.")
        if user.role == role:
            return user
        if user.role == "admin" and role == "user" and self.users.count_admins() <= 1:
            raise UserAdminError("Нельзя снять роль admin с последнего администратора.")
        return self.users.update_role(user_id, role)

    def delete_user(self, user_id: int) -> None:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserAdminError("Пользователь не найден.")
        if user.role == "admin" and self.users.count_admins() <= 1:
            raise UserAdminError("Нельзя удалить последнего администратора.")
        self.users.delete_user(user_id)
