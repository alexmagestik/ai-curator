from __future__ import annotations

from app.database.db import get_connection, init_db
from app.database.models import ChatSession, Message, User, UserProfile, utc_now_iso
from app.utils.config import Settings, get_settings

VALID_ROLES = ("user", "admin")


class UserRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: str = "user",
    ) -> User:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")

        created_at = utc_now_iso()
        with get_connection(self.settings) as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (email.strip().lower(), password_hash, role, created_at),
            )
            user_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO user_profiles (user_id, current_level, confidence, updated_at)
                VALUES (?, 'intermediate', 0.5, ?)
                """,
                (user_id, created_at),
            )
            connection.commit()
        return User(id=user_id, email=email.strip().lower(), role=role, created_at=created_at)

    def get_by_email(self, email: str) -> tuple[User, str] | None:
        with get_connection(self.settings) as connection:
            row = connection.execute(
                "SELECT id, email, password_hash, role, created_at FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        if row is None:
            return None
        user = User(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            created_at=row["created_at"],
        )
        return user, row["password_hash"]

    def get_by_id(self, user_id: int) -> User | None:
        with get_connection(self.settings) as connection:
            row = connection.execute(
                "SELECT id, email, role, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return User(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            created_at=row["created_at"],
        )

    def get_profile(self, user_id: int) -> UserProfile | None:
        with get_connection(self.settings) as connection:
            row = connection.execute(
                """
                SELECT user_id, current_level, confidence, updated_at
                FROM user_profiles WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return UserProfile(
            user_id=row["user_id"],
            current_level=row["current_level"],
            confidence=row["confidence"],
            updated_at=row["updated_at"],
        )

    def email_exists(self, email: str) -> bool:
        with get_connection(self.settings) as connection:
            row = connection.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        return row is not None

    def update_user_level(
        self,
        user_id: int,
        level: str,
        confidence: float,
    ) -> UserProfile:
        if level not in ("beginner", "intermediate", "advanced"):
            level = "intermediate"
        updated_at = utc_now_iso()
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                UPDATE user_profiles
                SET current_level = ?, confidence = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (level, confidence, updated_at, user_id),
            )
            connection.commit()
        profile = self.get_profile(user_id)
        if profile is None:
            raise ValueError(f"Profile not found for user {user_id}")
        return profile


class ChatRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def create_session(self, user_id: int, title: str = "Новый диалог") -> ChatSession:
        started_at = utc_now_iso()
        with get_connection(self.settings) as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_sessions (user_id, title, started_at)
                VALUES (?, ?, ?)
                """,
                (user_id, title, started_at),
            )
            session_id = int(cursor.lastrowid)
            connection.commit()
        return ChatSession(
            id=session_id,
            user_id=user_id,
            title=title,
            started_at=started_at,
            message_count=0,
        )

    def get_session(self, session_id: int, user_id: int) -> ChatSession | None:
        with get_connection(self.settings) as connection:
            row = connection.execute(
                """
                SELECT s.id, s.user_id, s.title, s.started_at,
                       COUNT(m.id) AS message_count
                FROM chat_sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.id = ? AND s.user_id = ?
                GROUP BY s.id
                """,
                (session_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return ChatSession(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            started_at=row["started_at"],
            message_count=row["message_count"],
        )

    def list_sessions(self, user_id: int) -> list[ChatSession]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.user_id, s.title, s.started_at,
                       COUNT(m.id) AS message_count
                FROM chat_sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.user_id = ?
                GROUP BY s.id
                ORDER BY s.started_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            ChatSession(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                started_at=row["started_at"],
                message_count=row["message_count"],
            )
            for row in rows
        ]

    def search_sessions(self, user_id: int, query: str) -> list[ChatSession]:
        pattern = f"%{query.strip()}%"
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT s.id, s.user_id, s.title, s.started_at,
                       COUNT(m.id) AS message_count
                FROM chat_sessions s
                JOIN messages m ON m.session_id = s.id
                WHERE s.user_id = ? AND m.content LIKE ?
                GROUP BY s.id
                ORDER BY s.started_at DESC
                """,
                (user_id, pattern),
            ).fetchall()
        return [
            ChatSession(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                started_at=row["started_at"],
                message_count=row["message_count"],
            )
            for row in rows
        ]

    def update_session_title(self, session_id: int, title: str) -> None:
        with get_connection(self.settings) as connection:
            connection.execute(
                "UPDATE chat_sessions SET title = ? WHERE id = ?",
                (title, session_id),
            )
            connection.commit()

    def add_message(self, session_id: int, role: str, content: str) -> Message:
        created_at = utc_now_iso()
        with get_connection(self.settings) as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, created_at),
            )
            message_id = int(cursor.lastrowid)
            connection.commit()
        return Message(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=created_at,
        )

    def get_messages(
        self,
        session_id: int,
        *,
        limit: int | None = None,
    ) -> list[Message]:
        query = """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
        """
        params: tuple = (session_id,)
        if limit is not None:
            query = """
                SELECT id, session_id, role, content, created_at
                FROM (
                    SELECT id, session_id, role, content, created_at
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC
            """
            params = (session_id, limit)

        with get_connection(self.settings) as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            Message(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
