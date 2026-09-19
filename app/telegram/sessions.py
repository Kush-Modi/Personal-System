"""Telegram user session management for interactive edits."""

from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.database.repositories.edit_session import EditSessionRepository
from app.domain.models import EditSession


class TelegramSessionManager:
    """Manages active interactive edit sessions backed by SQLite with TTL expiration."""

    def __init__(
        self,
        session_repo: Optional[EditSessionRepository] = None,
        ttl_minutes: Optional[int] = None
    ):
        self.repo = session_repo or EditSessionRepository()
        self.ttl_minutes = ttl_minutes if ttl_minutes is not None else settings.edit_session_ttl_minutes

    def start_edit_session(self, user_id: int, pending_item_id: int, item_type: str) -> None:
        """Start or refresh an active edit session for a user."""
        expires_at = (datetime.now() + timedelta(minutes=self.ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        self.repo.upsert_session(
            user_id=user_id,
            pending_item_id=pending_item_id,
            item_type=item_type,
            expires_at=expires_at
        )

    def get_active_session(self, user_id: int) -> Optional[EditSession]:
        """Fetch active unexpired session for user."""
        return self.repo.get_session(user_id)

    def end_session(self, user_id: int) -> bool:
        """Clear active session for user."""
        return self.repo.delete_session(user_id)
