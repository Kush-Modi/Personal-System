"""Database connection management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("database.connection")


def get_raw_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Create and configure a raw SQLite connection."""
    target_path = Path(db_path) if db_path else settings.database_path
    
    # Ensure directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(target_path),
        timeout=10.0,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    
    # Performance & integrity pragmas
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    
    return conn


@contextmanager
def open_connection(
    db_path: Optional[Union[str, Path]] = None,
    commit: bool = True
) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that guarantees connection closing and transaction commit/rollback."""
    conn = get_raw_connection(db_path)
    try:
        yield conn
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def get_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Backward-compatible helper returning a raw connection."""
    return get_raw_connection(db_path)
