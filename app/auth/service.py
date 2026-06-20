from __future__ import annotations

from dataclasses import dataclass

from app.auth.passwords import hash_password, verify_password
from app.database.models import User
from app.database.repository import UserRepository


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class AuthResult:
    user: User


class AuthService:
    def __init__(self, user_repository: UserRepository | None = None) -> None:
        self.users = user_repository or UserRepository()

    def register(self, email: str, password: str, role: str = "user") -> AuthResult:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise AuthError("Укажите корректный email.")
        if len(password) < 6:
            raise AuthError("Пароль должен содержать минимум 6 символов.")
        if self.users.email_exists(email):
            raise AuthError("Пользователь с таким email уже зарегистрирован.")

        user = self.users.create_user(
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        return AuthResult(user=user)

    def login(self, email: str, password: str) -> AuthResult:
        record = self.users.get_by_email(email)
        if record is None:
            raise AuthError("Неверный email или пароль.")

        user, password_hash = record
        if not verify_password(password, password_hash):
            raise AuthError("Неверный email или пароль.")

        return AuthResult(user=user)

    def get_user(self, user_id: int) -> User | None:
        return self.users.get_by_id(user_id)
