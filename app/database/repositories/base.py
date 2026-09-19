"""Base repository interface and helpers."""

from pathlib import Path
from typing import Optional, Union
from app.database.connection import open_connection


class BaseRepository:
    """Base class for all SQLite repositories."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = db_path

    def connection(self, commit: bool = True):
        """Get managed database connection context that auto-closes."""
        return open_connection(self.db_path, commit=commit)
