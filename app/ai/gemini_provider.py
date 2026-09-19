"""Gemini AI Provider implementation skeleton (Phase 1 architectural prep)."""

from pathlib import Path
from typing import Optional, Union

from app.ai.provider import AIProvider
from app.ai.schemas import FoodExtractionResult, ReceiptExtractionResult
from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger

logger = get_logger("ai.gemini")


class GeminiProvider(AIProvider):
    """Google Gemini AI perception provider implementation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key

    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def extract_food_from_image(
        self,
        image_path: Union[str, Path],
        context_prompt: str = ""
    ) -> FoodExtractionResult:
        """
        Placeholder for Phase 4: Gemini Multimodal Vision API integration.
        In Phase 1, validates configuration readiness.
        """
        if not self.is_available():
            raise AIServiceError("GEMINI_API_KEY is not configured.")
        
        logger.info(f"Preparing food extraction for image: {image_path}")
        # Full API calling logic will be implemented in Phase 4
        raise NotImplementedError("Live vision extraction will be enabled in Phase 4.")

    def extract_receipt_from_image(
        self,
        image_path: Union[str, Path]
    ) -> ReceiptExtractionResult:
        """
        Placeholder for Phase 4: Receipt extraction.
        In Phase 1, validates configuration readiness.
        """
        if not self.is_available():
            raise AIServiceError("GEMINI_API_KEY is not configured.")
        
        logger.info(f"Preparing receipt extraction for image: {image_path}")
        raise NotImplementedError("Live receipt extraction will be enabled in Phase 4.")
