"""Tests for AIService orchestration, memory integration, and telemetry logging."""

import tempfile
import unittest
from pathlib import Path

from app.ai.budget import AIBudgetManager
from app.ai.provider import AIProvider
from app.ai.router import AIRouter
from app.ai.schemas import ExtractedFoodItem, FoodExtractionResult, ReceiptExtractionResult
from app.ai.service import AIService
from app.database.migrations import run_migrations
from app.database.repositories.ai_provider_health import AIProviderHealthRepository
from app.database.repositories.ai_request import AIRequestRepository
from app.database.repositories.food_memory import FoodMemoryRepository
from app.domain.models import InputSource, ItemType, PendingStatus
from app.input.ai_processor import AIInputProcessor
from app.services.food_memory.service import FoodMemoryService
from app.services.pending.service import PendingItemService


class MockTextAndVisionProvider(AIProvider):
    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    def generate_structured(self, request):
        raise NotImplementedError()

    def extract_food_from_image(self, image_path, context_prompt="", memory_context=""):
        return FoodExtractionResult(
            items=[
                ExtractedFoodItem(food_name="Paneer Tikka", estimated_calories=320.0, confidence=0.9),
                ExtractedFoodItem(food_name="Green Chutney", estimated_calories=30.0, confidence=0.85),
            ],
            notes="Identified grilled paneer cubes with mint chutney",
            provider="gemini",
            model="gemini-2.5-flash"
        )

    def extract_food_from_text(self, text, memory_context=""):
        return FoodExtractionResult(
            items=[
                ExtractedFoodItem(food_name="2 Boiled Eggs", estimated_calories=150.0, confidence=0.95),
            ],
            notes="High protein breakfast",
            provider="gemini",
            model="gemini-2.5-flash-lite"
        )

    def extract_receipt_from_image(self, image_path):
        return ReceiptExtractionResult()


class TestAIService(unittest.TestCase):
    """Test suite for complete AIService, AIInputProcessor, and pending confirmation cycle."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_ai_service.db"
        run_migrations(self.db_path)

        self.ai_request_repo = AIRequestRepository(self.db_path)
        self.food_memory_repo = FoodMemoryRepository(self.db_path)
        self.food_memory_service = FoodMemoryService(self.food_memory_repo)
        self.budget_manager = AIBudgetManager(ai_request_repo=self.ai_request_repo, daily_request_limit=10)
        self.health_repo = AIProviderHealthRepository(self.db_path)

        # Mock router with mock provider and scoped health_repo
        self.mock_provider = MockTextAndVisionProvider()
        self.router = AIRouter(
            providers={"gemini": self.mock_provider},
            health_repo=self.health_repo
        )

        self.ai_service = AIService(
            router=self.router,
            budget_manager=self.budget_manager,
            food_memory_service=self.food_memory_service,
            ai_request_repo=self.ai_request_repo
        )

        self.processor = AIInputProcessor(ai_service=self.ai_service)
        self.pending_service = PendingItemService(
            pending_repo=None,
            food_memory_service=self.food_memory_service
        )
        # Point pending repo and food repo to test DB
        self.pending_service.repo.db_path = self.db_path
        self.pending_service.food_service.repository.db_path = self.db_path

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_process_food_text_and_telemetry(self):
        res = self.ai_service.process_food_text("2 boiled eggs")
        self.assertEqual(len(res.items), 1)
        self.assertEqual(res.items[0].food_name, "2 Boiled Eggs")
        self.assertEqual(res.items[0].estimated_calories, 150.0)

        # Check telemetry logged in DB
        usage = self.ai_request_repo.get_daily_usage(self.budget_manager.get_current_date_str())
        self.assertEqual(usage["total_requests"], 1)
        self.assertEqual(usage["success_requests"], 1)

    def test_zero_ai_memory_match_shortcut(self):
        # Learn an item in memory first
        self.food_memory_service.record_confirmed_food("protein shake", 220.0, unit="scoop")

        # Now query exact memory match
        res = self.ai_service.process_food_text("protein shake")
        self.assertEqual(res.provider, "food_memory")
        self.assertTrue(res.items[0].memory_match)
        self.assertEqual(res.items[0].estimated_calories, 220.0)

        # Zero AI request logged in telemetry!
        usage = self.ai_request_repo.get_daily_usage(self.budget_manager.get_current_date_str())
        self.assertEqual(usage["total_requests"], 0)

    def test_input_processor_and_pending_confirmation_learning(self):
        # 1. Process natural text via processor
        proc_result = self.processor.process_text("had 2 boiled eggs")
        self.assertTrue(proc_result.success)
        self.assertEqual(proc_result.item_type, ItemType.FOOD.value)

        # 2. Create pending item
        pending_item = self.pending_service.create_pending_item(
            item_type=proc_result.item_type,
            structured_payload=proc_result.payload,
            source=InputSource.TEXT.value
        )
        self.assertEqual(pending_item.status, PendingStatus.PENDING.value)

        # 3. Confirm pending item -> saves to Food table and learns into Food Memory
        confirmed_item, domain_record = self.pending_service.confirm(pending_item.id)
        self.assertEqual(confirmed_item.status, PendingStatus.CONFIRMED.value)

        # 4. Verify food memory learned
        mem = self.food_memory_service.find_match("2 Boiled Eggs")
        self.assertIsNotNone(mem)
        self.assertEqual(mem.default_calories, 150.0)


if __name__ == "__main__":
    unittest.main()
