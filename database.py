"""
Database compatibility bridge.
Redirects legacy callers to the new modular database package and migrations.
"""

from pathlib import Path
from app.database.connection import get_connection as _get_connection
from app.database.migrations import run_migrations

DB_PATH = Path(__file__).parent / "personal.db"


def get_connection():
    """Backward-compatible connection getter."""
    return _get_connection(DB_PATH)


def init_db():
    """Backward-compatible database initializer executing safe migrations."""
    applied = run_migrations(DB_PATH)
    print(f"Database initialized/migrated successfully! ({applied} migrations applied)")


if __name__ == "__main__":
    init_db()
