"""Abstract base interface for AI perception and text providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

from app.ai.schemas import (
    AIRequest,
    AIResponse,
    FoodExtractionResult,
    IntentResult,
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

    def extract_intent_action(
        self,
        text: str,
        current_date: Optional[str] = None,
        memory_context: str = ""
    ) -> IntentResult:
        """Extract multi-domain intent, entities, and action from natural language input."""
        # Default implementation delegates to extract_food_from_text for backwards compatibility
        food_res = self.extract_food_from_text(text, memory_context=memory_context)
        return IntentResult(
            intent="FOOD",
            confidence=food_res.items[0].confidence if food_res.items else 0.85,
            response_mode="ACTION",
            action={
                "items": [
                    {
                        "name": item.food_name,
                        "quantity": item.quantity,
                        "unit": item.unit,
                        "estimated_calories": item.estimated_calories,
                    }
                    for item in food_res.items
                ],
                "total_calories": food_res.total_estimated_calories,
                "notes": food_res.notes,
                "meal_type": food_res.meal_type,
            },
            requires_confirmation=True,
            provider=food_res.provider,
            model=food_res.model,
            raw_response=food_res.raw_response,
        )


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
        image_path: Union[str, Path],
        caption: str = ""
    ) -> ReceiptExtractionResult:
        """Extract structured expense details from a receipt image."""
        pass


