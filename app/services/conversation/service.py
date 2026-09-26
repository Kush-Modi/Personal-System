"""Conversation context service managing multi-turn memory and follow-up adjustments."""

import uuid
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.database.repositories.conversation_context import (
    ConversationContextRecord,
    ConversationContextRepository,
)

logger = get_logger("services.conversation")


class ConversationContextService:
    """Service managing short-term conversation context for multi-turn user interactions."""

    def __init__(self, repo: Optional[ConversationContextRepository] = None, ttl_minutes: int = 15):
        self.repo = repo or ConversationContextRepository()
        self.ttl_minutes = ttl_minutes

    def get_context(self, user_id: int) -> Optional[ConversationContextRecord]:
        """Fetch active unexpired context for user."""
        return self.repo.get(user_id)

    def record_turn(
        self,
        user_id: int,
        user_message: str,
        bot_response: str,
        intent: Optional[str] = None,
        active_pending_id: Optional[int] = None
    ) -> None:
        """Record a conversation turn with bounded message history."""
        existing = self.repo.get(user_id)
        context_id = existing.context_id if existing else str(uuid.uuid4())
        messages = existing.recent_messages if existing else []

        messages.append({"role": "user", "text": user_message})
        messages.append({"role": "assistant", "text": bot_response})

        # Keep last 6 messages (3 turns)
        bounded_messages = messages[-6:]

        pending_id = active_pending_id if active_pending_id is not None else (existing.active_pending_id if existing else None)
        last_intent = intent or (existing.last_intent if existing else None)

        self.repo.save(
            user_id=user_id,
            context_id=context_id,
            state="ACTIVE",
            last_intent=last_intent,
            active_pending_id=pending_id,
            recent_messages=bounded_messages,
            ttl_minutes=self.ttl_minutes
        )

    def clear_context(self, user_id: int) -> bool:
        """Clear context for user upon task/item completion or explicit cancel."""
        return self.repo.clear(user_id)
