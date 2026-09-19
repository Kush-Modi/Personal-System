"""Edit session repository for managing short-lived user edit interactions."""

from datetime import datetime
from typing import Optional

from app.database.repositories.base import BaseRepository
from app.domain.models import EditSession


class EditSessionRepository(BaseRepository):
    """Repository handling active interactive edit state per user."""

    def upsert_session(
        self,
        user_id: int,
        pending_item_id: int,
        item_type: str,
        expires_at: str
    ) -> None:
        """Create or replace an active edit session for a user."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO edit_sessions (user_id, pending_item_id, item_type, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    pending_item_id = excluded.pending_item_id,
                    item_type = excluded.item_type,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at;
                """,
                (user_id, pending_item_id, item_type.upper(), now_str, expires_at)
            )

    def get_session(self, user_id: int) -> Optional[EditSession]:
        """Fetch active edit session for a user if not expired."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, pending_item_id, item_type, created_at, expires_at
                FROM edit_sessions
                WHERE user_id = ? AND expires_at >= ?;
                """,
                (user_id, now_str)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return EditSession(
                user_id=row["user_id"],
                pending_item_id=row["pending_item_id"],
                item_type=row["item_type"],
                created_at=row["created_at"],
                expires_at=row["expires_at"]
            )

    def delete_session(self, user_id: int) -> bool:
        """Remove user edit session."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM edit_sessions WHERE user_id = ?;", (user_id,))
            return cursor.rowcount > 0

    def cleanup_expired(self) -> int:
        """Delete all expired edit sessions."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM edit_sessions WHERE expires_at < ?;", (now_str,))
            return cursor.rowcount
