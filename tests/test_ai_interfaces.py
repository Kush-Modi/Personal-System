"""Tests for AI provider interfaces, availability checks, and schemas."""

import unittest
from app.ai.gemini_provider import GeminiProvider
from app.ai.groq_provider import GroqProvider
from app.ai.openrouter_provider import OpenRouterProvider
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
from app.core.exceptions import AIServiceError


class TestAIInterfaces(unittest.TestCase):
    """Test AI interfaces, availability checks, and schemas."""

    def test_gemini_provider_availability(self):
        provider_no_key = GeminiProvider(api_key="")
        self.assertFalse(provider_no_key.is_available())

        provider_with_key = GeminiProvider(api_key="AIzaSyDummyKey123")
        self.assertTrue(provider_with_key.is_available())

    def test_groq_provider_availability(self):
        provider_no_key = GroqProvider(api_key="")
        self.assertFalse(provider_no_key.is_available())

        provider_with_key = GroqProvider(api_key="gsk_dummy_123")
        self.assertTrue(provider_with_key.is_available())

    def test_openrouter_provider_availability(self):
        provider_no_key = OpenRouterProvider(api_key="")
        self.assertFalse(provider_no_key.is_available())

        provider_with_key = OpenRouterProvider(api_key="sk-or-dummy")
        self.assertTrue(provider_with_key.is_available())

    def test_provider_raises_on_unconfigured_call(self):
        provider = GeminiProvider(api_key="")
        with self.assertRaises(AIServiceError):
            provider.extract_food_from_image("dummy.jpg")

        groq = GroqProvider(api_key="")
        with self.assertRaises(AIServiceError):
            groq.extract_food_from_text("apple")

        openrouter = OpenRouterProvider(api_key="")
        with self.assertRaises(AIServiceError):
            openrouter.extract_food_from_text("apple")

    def test_schemas(self):
        food_res = FoodExtractionResult(
            items=[ExtractedFoodItem(food_name="Apple", estimated_calories=95.0, confidence=0.95)]
        )
        self.assertEqual(len(food_res.items), 1)
        self.assertEqual(food_res.items[0].food_name, "Apple")
        self.assertEqual(food_res.total_estimated_calories, 95.0)

        receipt_res = ReceiptExtractionResult(
            merchant="Supermarket",
            total_amount=45.5,
            category="Groceries",
            items=[ExtractedReceiptItem(name="Milk", price=3.5)]
        )
        self.assertEqual(receipt_res.merchant, "Supermarket")
        self.assertEqual(receipt_res.total_amount, 45.5)


if __name__ == "__main__":
    unittest.main()
