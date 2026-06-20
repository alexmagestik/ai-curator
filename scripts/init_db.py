#!/usr/bin/env python3
"""Initialize SQLite database and optionally create admin user."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from app.auth.passwords import hash_password
from app.database.db import init_db
from app.database.repository import UserRepository
from app.utils.config import get_settings


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = get_settings()
    init_db(settings)
    print(f"Database initialized: {settings.database_path}")

    admin_email = os.getenv("INIT_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("INIT_ADMIN_PASSWORD", "")

    if admin_email and admin_password:
        users = UserRepository(settings)
        if users.email_exists(admin_email):
            print(f"Admin already exists: {admin_email}")
        else:
            users.create_user(admin_email, hash_password(admin_password), role="admin")
            print(f"Admin created: {admin_email}")
    else:
        print("Tip: set INIT_ADMIN_EMAIL and INIT_ADMIN_PASSWORD in .env to create admin.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
