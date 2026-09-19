"""AI package for multimodal perception, text reasoning, and usage telemetry."""

from app.ai.budget import AIBudgetManager
from app.ai.gemini_provider import GeminiProvider
from app.ai.groq_provider import GroqProvider
from app.ai.openrouter_provider import OpenRouterProvider
from app.ai.provider import AIProvider
from app.ai.router import AIRouter
from app.ai.schemas import (
    AIRequest,
    AIResponse,
    AITaskType,
    ExtractedFoodItem,
    ExtractedReceiptItem,
    FoodExtractionResult,
    ReceiptExtractionResult,
)
from app.ai.service import AIService

__all__ = [
    "AIProvider",
    "GeminiProvider",
    "GroqProvider",
    "OpenRouterProvider",
    "AIRouter",
    "AIBudgetManager",
    "AIService",
    "AIRequest",
    "AIResponse",
    "AITaskType",
    "ExtractedFoodItem",
    "FoodExtractionResult",
    "ExtractedReceiptItem",
    "ReceiptExtractionResult",
]
