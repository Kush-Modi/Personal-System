"""Conversation context repository for multi-turn short-term dialogue memory."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.database.repositories.base import BaseRepository


@dataclass
class ConversationContextRecord:
    user_id: int
    context_id: str
    state: str
    last_intent: Optional[str]
    active_pending_id: Optional[int]
    recent_messages: List[Dict[str, str]]
    updated_at: str
    expires_at: str


class ConversationContextRepository(BaseRepository):
    """Repository handling short-term conversation context storage and retrieval."""

    def get(self, user_id: int) -> Optional[ConversationContextRecord]:
        """Fetch active unexpired conversation context for user."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, context_id, state, last_intent, active_pending_id, recent_messages_json, updated_at, expires_at
                FROM conversation_context
                WHERE user_id = ? AND datetime(expires_at) > datetime('now');
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            msgs = []
            if row["recent_messages_json"]:
                try:
                    msgs = json.loads(row["recent_messages_json"])
                except Exception:
                    msgs = []

            return ConversationContextRecord(
                user_id=row["user_id"],
                context_id=row["context_id"],
                state=row["state"],
                last_intent=row["last_intent"],
                active_pending_id=row["active_pending_id"],
                recent_messages=msgs,
                updated_at=row["updated_at"],
                expires_at=row["expires_at"]
            )

    def save(
        self,
        user_id: int,
        context_id: str,
        state: str = "ACTIVE",
        last_intent: Optional[str] = None,
        active_pending_id: Optional[int] = None,
        recent_messages: Optional[List[Dict[str, str]]] = None,
        ttl_minutes: int = 15
    ) -> None:
        """Upsert conversation context with TTL."""
        msgs_json = json.dumps(recent_messages or [])
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversation_context (
                    user_id, context_id, state, last_intent, active_pending_id, recent_messages_json,
                    updated_at, expires_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, datetime('now', '+' || ? || ' minutes')
                )
                ON CONFLICT(user_id) DO UPDATE SET
                    context_id = excluded.context_id,
                    state = excluded.state,
                    last_intent = excluded.last_intent,
                    active_pending_id = excluded.active_pending_id,
                    recent_messages_json = excluded.recent_messages_json,
                    updated_at = CURRENT_TIMESTAMP,
                    expires_at = datetime('now', '+' || ? || ' minutes');
                """,
                (user_id, context_id, state, last_intent, active_pending_id, msgs_json, ttl_minutes, ttl_minutes)
            )

    def clear(self, user_id: int) -> bool:
        """Clear conversation context for a user."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversation_context WHERE user_id = ?;", (user_id,))
            return cursor.rowcount > 0

    def purge_expired(self) -> int:
        """Purge all expired conversation contexts."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversation_context WHERE datetime(expires_at) <= datetime('now');")
            return cursor.rowcount
