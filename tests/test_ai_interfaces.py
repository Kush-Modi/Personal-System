"""Tests for AI abstractions and schemas."""

import unittest
from app.ai.gemini_provider import GeminiProvider
from app.ai.schemas import (
    ExtractedFoodItem,
    FoodExtractionResult,
    ExtractedReceiptItem,
    ReceiptExtractionResult,
)
from app.ai.service import AIService
from app.core.exceptions import AIServiceError


class TestAIInterfaces(unittest.TestCase):
    """Test AI interfaces, availability checks, and schemas."""

    def test_provider_availability(self):
        provider_no_key = GeminiProvider(api_key="")
        self.assertFalse(provider_no_key.is_available())

        provider_with_key = GeminiProvider(api_key="AIzaSyDummyKey123")
        self.assertTrue(provider_with_key.is_available())

        ai_service = AIService(provider_with_key)
        self.assertTrue(ai_service.is_ai_enabled())

    def test_provider_raises_on_unconfigured_call(self):
        provider = GeminiProvider(api_key="")
        with self.assertRaises(AIServiceError):
            provider.extract_food_from_image("dummy.jpg")

    def test_schemas(self):
        food_res = FoodExtractionResult(
            items=[ExtractedFoodItem(food_name="Apple", estimated_calories=95.0, confidence=0.95)]
        )
        self.assertEqual(len(food_res.items), 1)
        self.assertEqual(food_res.items[0].food_name, "Apple")

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
