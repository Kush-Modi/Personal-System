"""Tests for AIRouter failover, capability matching, and circuit breaking."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.ai.provider import AIProvider
from app.ai.router import AIRouter
from app.ai.schemas import ExtractedFoodItem, FoodExtractionResult
from app.core.exceptions import AIRateLimitError, AIServiceError
from app.database.migrations import run_migrations
from app.database.repositories.ai_provider_health import (
    AIProviderHealthRepository,
)


class MockVisionProvider(AIProvider):
    def __init__(self, name: str, will_fail: bool = False):
        self._name = name
        self.will_fail = will_fail

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    def generate_structured(self, request):
        raise NotImplementedError()

    def extract_food_from_image(self, image_path, context_prompt="", memory_context=""):
        if self.will_fail:
            raise AIRateLimitError(f"{self._name} simulated rate limit")
        return FoodExtractionResult(
            items=[ExtractedFoodItem(food_name="Dosa", estimated_calories=250.0)],
            provider=self._name,
            model="test-vision"
        )

    def extract_food_from_text(self, text, memory_context=""):
        if self.will_fail:
            raise AIRateLimitError(f"{self._name} simulated rate limit")
        return FoodExtractionResult(
            items=[ExtractedFoodItem(food_name="Dosa", estimated_calories=250.0)],
            provider=self._name,
            model="test-text"
        )

    def extract_receipt_from_image(self, image_path):
        raise NotImplementedError()


class TestAIRouter(unittest.TestCase):
    """Test suite for AIRouter multi-provider fallback and circuit breakers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_router.db"
        run_migrations(self.db_path)
        self.health_repo = AIProviderHealthRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_primary_route(self):
        providers = {
            "gemini": MockVisionProvider("gemini", will_fail=False),
            "groq": MockVisionProvider("groq", will_fail=False),
        }
        router = AIRouter(providers=providers, health_repo=self.health_repo)

        result, fallback = router.route_food_text("1 masala dosa")
        self.assertEqual(result.provider, "gemini")
        self.assertFalse(fallback)
        self.assertEqual(len(result.items), 1)

    def test_failover_to_secondary_provider(self):
        providers = {
            "gemini": MockVisionProvider("gemini", will_fail=True),
            "groq": MockVisionProvider("groq", will_fail=False),
            "openrouter": MockVisionProvider("openrouter", will_fail=False),
        }
        router = AIRouter(providers=providers, health_repo=self.health_repo)

        result, fallback = router.route_food_text("1 masala dosa")
        self.assertEqual(result.provider, "groq")
        self.assertTrue(fallback)

        # Gemini failure should be recorded
        g_health = self.health_repo.get_health("gemini")
        self.assertIsNotNone(g_health)
        self.assertEqual(g_health.consecutive_failures, 1)


if __name__ == "__main__":
    unittest.main()
