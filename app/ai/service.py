"""AI Service orchestrating perception providers and pending items."""

from pathlib import Path
from typing import Optional, Union

from app.ai.gemini_provider import GeminiProvider
from app.ai.provider import AIProvider
from app.database.repositories.pending_items import PendingItemRepository


class AIService:
    """Service mediating between Telegram inputs, AI providers, and pending item staging."""

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        pending_repo: Optional[PendingItemRepository] = None
    ):
        self.provider = provider or GeminiProvider()
        self.pending_repo = pending_repo or PendingItemRepository()

    def is_ai_enabled(self) -> bool:
        """Check if underlying AI provider is ready."""
        return self.provider.is_available()
