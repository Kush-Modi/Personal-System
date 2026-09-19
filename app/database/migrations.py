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


def _migration_003_phase2_pending_and_edit_sessions(conn: sqlite3.Connection) -> None:
    """Enhance pending_items schema and add edit_sessions table for Phase 2 workflow."""
    cursor = conn.cursor()

    # Inspect columns of pending_items
    cursor.execute("PRAGMA table_info(pending_items);")
    existing_cols = {row[1] for row in cursor.fetchall()}

    if "source" not in existing_cols:
        cursor.execute("ALTER TABLE pending_items ADD COLUMN source TEXT DEFAULT 'UNKNOWN';")
    if "confidence" not in existing_cols:
        cursor.execute("ALTER TABLE pending_items ADD COLUMN confidence REAL DEFAULT 1.0;")
    if "updated_at" not in existing_cols:
        cursor.execute("ALTER TABLE pending_items ADD COLUMN updated_at TEXT;")
    if "expires_at" not in existing_cols:
        cursor.execute("ALTER TABLE pending_items ADD COLUMN expires_at TEXT;")
    if "error_info" not in existing_cols:
        cursor.execute("ALTER TABLE pending_items ADD COLUMN error_info TEXT;")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_items_expires_at ON pending_items (expires_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_items_created_at ON pending_items (created_at);")

    # Edit sessions table for short-lived interactive edits
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edit_sessions (
            user_id INTEGER PRIMARY KEY,
            pending_item_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (pending_item_id) REFERENCES pending_items (id) ON DELETE CASCADE
        );
    """)


def _migration_004_phase3_ai_telemetry_and_food_memory(conn: sqlite3.Connection) -> None:
    """Create food_memory, ai_requests telemetry, and ai_provider_health tables for Phase 3."""
    cursor = conn.cursor()

    # Food Memory: local memory of learned user food items and caloric values
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL UNIQUE,
            aliases_json TEXT,
            default_calories REAL NOT NULL,
            default_unit TEXT DEFAULT 'serving',
            default_portion_grams REAL,
            confidence REAL DEFAULT 1.0,
            source TEXT NOT NULL DEFAULT 'USER_CONFIRMED',
            use_count INTEGER DEFAULT 1,
            last_used_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_food_memory_canonical ON food_memory (canonical_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_food_memory_last_used ON food_memory (last_used_at);")

    # AI Requests: structured telemetry for all AI provider calls and budget auditing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL UNIQUE,
            task_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            latency_ms REAL DEFAULT 0.0,
            status TEXT NOT NULL,
            error_type TEXT,
            error_message TEXT,
            fallback_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_requests_created_at ON ai_requests (created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_requests_provider ON ai_requests (provider);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_requests_status ON ai_requests (status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_requests_task_type ON ai_requests (task_type);")

    # AI Provider Health: provider circuit breakers and operational telemetry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_provider_health (
            provider TEXT PRIMARY KEY,
            consecutive_failures INTEGER DEFAULT 0,
            circuit_open_until TEXT,
            last_success_at TEXT,
            last_failure_at TEXT,
            last_error TEXT,
            total_requests INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)


# Registry of ordered migrations
MIGRATIONS: List[Migration] = [
    Migration(version=1, name="baseline_tables", up=_migration_001_baseline),
    Migration(version=2, name="performance_indexes_and_pending_items", up=_migration_002_performance_indexes_and_pending_items),
    Migration(version=3, name="phase2_pending_and_edit_sessions", up=_migration_003_phase2_pending_and_edit_sessions),
    Migration(version=4, name="phase3_ai_telemetry_and_food_memory", up=_migration_004_phase3_ai_telemetry_and_food_memory),
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
