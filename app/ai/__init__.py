"""AI package for future multimodal extraction workflows."""

from app.ai.provider import AIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.service import AIService
from app.ai.schemas import (
    ExtractedFoodItem,
    FoodExtractionResult,
    ExtractedReceiptItem,
    ReceiptExtractionResult,
)

__all__ = [
    "AIProvider",
    "GeminiProvider",
    "AIService",
    "ExtractedFoodItem",
    "FoodExtractionResult",
    "ExtractedReceiptItem",
    "ReceiptExtractionResult",
]
