"""Abstract base interface for AI perception providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from app.ai.schemas import FoodExtractionResult, ReceiptExtractionResult


class AIProvider(ABC):
    """Abstract interface for AI model providers (e.g. Gemini, Local LLM)."""

    @abstractmethod
    def extract_food_from_image(
        self,
        image_path: Union[str, Path],
        context_prompt: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items and estimated calories from an image."""
        pass

    @abstractmethod
    def extract_receipt_from_image(
        self,
        image_path: Union[str, Path]
    ) -> ReceiptExtractionResult:
        """Extract structured expense details from a receipt image."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        pass
