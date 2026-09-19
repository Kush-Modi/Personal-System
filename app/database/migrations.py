"""Database schema versioning and migration manager."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Union

from app.core.config import settings
from app.core.exceptions import MigrationError
from app.core.logging import get_logger
from app.database.connection import get_connection

logger = get_logger("database.migrations")


@dataclass
class Migration:
    version: int
    name: str
    up: Callable[[sqlite3.Connection], None]


def _migration_001_baseline(conn: sqlite3.Connection) -> None:
    """Create baseline tables for food, weights, and expenses if they don't already exist."""
    cursor = conn.cursor()
    
    # Weight records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weight REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Expense records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Food records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_name TEXT NOT NULL,
            calories REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)


def _migration_002_performance_indexes_and_pending_items(conn: sqlite3.Connection) -> None:
    """Add query indexes and create pending_items table for future AI workflows."""
    cursor = conn.cursor()

    # Query performance indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_food_created_at ON food (created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_weights_created_at ON weights (created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_created_at ON expenses (created_at);")

    # Pending items table for future AI ingestion pipeline
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            raw_payload TEXT,
            structured_payload TEXT NOT NULL,
            image_path TEXT,
            user_notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_items_status ON pending_items (status);")


# Registry of ordered migrations
MIGRATIONS: List[Migration] = [
    Migration(version=1, name="baseline_tables", up=_migration_001_baseline),
    Migration(version=2, name="performance_indexes_and_pending_items", up=_migration_002_performance_indexes_and_pending_items),
]


def init_version_table(conn: sqlite3.Connection) -> None:
    """Ensure schema_version table exists."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


def get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Retrieve set of applied migration versions."""
    init_version_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_version ORDER BY version ASC;")
    return {row[0] for row in cursor.fetchall()}


def run_migrations(db_path: Optional[Union[str, Path]] = None) -> int:
    """Run all pending database migrations safely."""
    conn = get_connection(db_path)
    applied_count = 0

    try:
        applied_versions = get_applied_versions(conn)

        for migration in MIGRATIONS:
            if migration.version not in applied_versions:
                logger.info(f"Applying migration v{migration.version:03d}: {migration.name}...")
                try:
                    conn.execute("BEGIN TRANSACTION;")
                    migration.up(conn)
                    conn.execute(
                        "INSERT INTO schema_version (version, name) VALUES (?, ?);",
                        (migration.version, migration.name)
                    )
                    conn.commit()
                    applied_count += 1
                    logger.info(f"Migration v{migration.version:03d} applied successfully.")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Migration v{migration.version:03d} failed: {e}", exc_info=True)
                    raise MigrationError(f"Migration v{migration.version:03d} failed: {e}") from e

        return applied_count
    finally:
        conn.close()
