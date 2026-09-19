"""Abstract base interface for AI perception and text providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

from app.ai.schemas import (
    AIRequest,
    AIResponse,
    FoodExtractionResult,
    ReceiptExtractionResult,
)


class AIProvider(ABC):
    """Abstract interface for AI model providers (e.g. Gemini, Groq, OpenRouter)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier name (e.g. 'gemini', 'groq', 'openrouter')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available (e.g. API key present)."""
        pass

    @abstractmethod
    def supports_vision(self) -> bool:
        """Check if provider supports image/multimodal input."""
        pass

    @abstractmethod
    def generate_structured(self, request: AIRequest) -> AIResponse:
        """Generate structured response conforming to the request schema."""
        pass

    @abstractmethod
    def extract_food_from_image(
        self,
        image_path: Union[str, Path],
        context_prompt: str = "",
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items and estimated calories from an image."""
        pass

    @abstractmethod
    def extract_food_from_text(
        self,
        text: str,
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items and estimated calories from natural language text."""
        pass

    @abstractmethod
    def extract_receipt_from_image(
        self,
        image_path: Union[str, Path]
    ) -> ReceiptExtractionResult:
        """Extract structured expense details from a receipt image."""
        pass
