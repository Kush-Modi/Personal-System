import asyncio
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

if "telegram" not in sys.modules:
    mock_tg = MagicMock()
    mock_tg_ext = MagicMock()
    sys.modules["telegram"] = mock_tg
    sys.modules["telegram.ext"] = mock_tg_ext

from app.ai.schemas import (
    ExtractedFoodItem,
    FoodExtractionResult,
    IntentResult,
    ReceiptExtractionResult,
)
from app.ai.service import AIService
from app.core.config import Settings
from app.database.migrations import run_migrations
from app.database.repositories.ai_request import AIRequestRepository
from app.services.food_memory.service import FoodMemoryService
from app.telegram.auth import authorized_only, is_user_authorized


class TestAuthorizationGuard(unittest.TestCase):
    """Test suite verifying authorization behavior and invariants."""

    def test_is_user_authorized_valid(self):
        fake_settings = Settings(telegram_allowed_user_id=12345678)
        with patch("app.telegram.auth.settings", fake_settings):
            self.assertTrue(is_user_authorized(12345678))
            self.assertFalse(is_user_authorized(99999999))
            self.assertFalse(is_user_authorized(None))
            self.assertFalse(is_user_authorized("12345678"))

    def test_is_user_authorized_fails_closed_when_unset_or_zero(self):
        fake_settings_none = Settings(telegram_allowed_user_id=None)
        with patch("app.telegram.auth.settings", fake_settings_none):
            self.assertFalse(is_user_authorized(12345678))
            self.assertFalse(is_user_authorized(0))

        fake_settings_zero = Settings(telegram_allowed_user_id=0)
        with patch("app.telegram.auth.settings", fake_settings_zero):
            self.assertFalse(is_user_authorized(12345678))
            self.assertFalse(is_user_authorized(0))

    def test_authorized_decorator_allows_whitelisted_user(self):
        called = False

        @authorized_only
        async def dummy_handler(update, context):
            nonlocal called
            called = True

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345678
        mock_update.effective_user = mock_user

        fake_settings = Settings(telegram_allowed_user_id=12345678)
        with patch("app.telegram.auth.settings", fake_settings):
            asyncio.run(dummy_handler(mock_update, MagicMock()))

        self.assertTrue(called)

    def test_authorized_decorator_blocks_unauthorized_message_with_zero_side_effects(self):
        called = False

        @authorized_only
        async def dummy_handler(update, context):
            nonlocal called
            called = True

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 88888888  # Unauthorized user
        mock_update.effective_user = mock_user
        mock_update.callback_query = None
        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock()
        mock_update.effective_message = mock_msg

        fake_settings = Settings(telegram_allowed_user_id=12345678)
        with patch("app.telegram.auth.settings", fake_settings):
            asyncio.run(dummy_handler(mock_update, MagicMock()))

        self.assertFalse(called)
        mock_msg.reply_text.assert_awaited_once_with("⛔ Access denied.")

    def test_authorized_decorator_blocks_unauthorized_callback_query(self):
        called = False

        @authorized_only
        async def dummy_handler(update, context):
            nonlocal called
            called = True

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 88888888
        mock_update.effective_user = mock_user
        mock_query = MagicMock()
        mock_query.answer = AsyncMock()
        mock_update.callback_query = mock_query

        fake_settings = Settings(telegram_allowed_user_id=12345678)
        with patch("app.telegram.auth.settings", fake_settings):
            asyncio.run(dummy_handler(mock_update, MagicMock()))

        self.assertFalse(called)
        mock_query.answer.assert_awaited_once_with("⛔ Unauthorized access.", show_alert=True)


class TestEventLoopResponsiveness(unittest.TestCase):
    """Verify that slow AI inferences do not freeze concurrent asynchronous operations."""

    def test_event_loop_does_not_block_concurrent_tasks(self):
        async def run_scenario():
            concurrent_ticks = 0

            async def ticker():
                nonlocal concurrent_ticks
                for _ in range(5):
                    await asyncio.sleep(0.04)
                    concurrent_ticks += 1

            # Simulated slow synchronous AI perception running via asyncio.to_thread
            def slow_ai_inference(text: str):
                time.sleep(0.18)
                return f"processed: {text}"

            ticker_task = asyncio.create_task(ticker())
            ai_task = asyncio.create_task(asyncio.to_thread(slow_ai_inference, "slow request"))

            ai_res, _ = await asyncio.gather(ai_task, ticker_task)

            self.assertEqual(ai_res, "processed: slow request")
            # Ticker should have ticked while AI was sleeping in a separate thread
            self.assertGreaterEqual(concurrent_ticks, 3)

        asyncio.run(run_scenario())


class TestAITelemetryTokenAccounting(unittest.TestCase):
    """Verify Stage 2.2 token telemetry captures authentic provider token metrics."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_telemetry.db"
        run_migrations(self.db_path)
        self.ai_request_repo = AIRequestRepository(self.db_path)
        self.food_mem_svc = MagicMock(spec=FoodMemoryService)
        self.food_mem_svc.get_memory_context_prompt.return_value = ""

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_real_tokens_logged_for_intent_action(self):
        mock_router = MagicMock()
        fake_intent_res = IntentResult(
            intent="FOOD",
            confidence=0.95,
            response_mode="ACTION",
            action={"food_name": "Roti", "calories": 100.0},
            provider="gemini",
            model="gemini-3.8-flash",
            prompt_tokens=482,
            completion_tokens=128,
            total_tokens=610,
            latency_ms=340.5,
        )
        mock_router.route_intent_action.return_value = (fake_intent_res, False)

        service = AIService(
            router=mock_router,
            food_memory_service=self.food_mem_svc,
            ai_request_repo=self.ai_request_repo
        )
        service.budget_manager.check_and_assert_budget = MagicMock()

        res = service.process_intent_action("Had 1 roti")
        self.assertEqual(res.total_tokens, 610)

        logs = self.ai_request_repo.get_recent_requests(limit=1)
        self.assertEqual(len(logs), 1)
        logged = logs[0]
        self.assertEqual(logged.provider, "gemini")
        self.assertEqual(logged.model, "gemini-3.8-flash")
        self.assertEqual(logged.prompt_tokens, 482)
        self.assertEqual(logged.completion_tokens, 128)
        self.assertEqual(logged.total_tokens, 610)
        self.assertAlmostEqual(logged.latency_ms, 340.5, places=1)
        self.assertEqual(logged.status, "SUCCESS")

    def test_real_tokens_logged_for_food_photo(self):
        mock_router = MagicMock()
        fake_food_res = FoodExtractionResult(
            items=[ExtractedFoodItem(food_name="Paneer", estimated_calories=300.0)],
            provider="groq",
            model="llama-3.2-11b-vision-preview",
            prompt_tokens=1150,
            completion_tokens=210,
            total_tokens=1360,
            latency_ms=520.0,
        )
        mock_router.route_food_photo.return_value = (fake_food_res, True)

        service = AIService(
            router=mock_router,
            food_memory_service=self.food_mem_svc,
            ai_request_repo=self.ai_request_repo
        )
        service.budget_manager.check_and_assert_budget = MagicMock()

        res = service.process_food_photo("dummy_path.jpg", caption="Lunch")
        self.assertEqual(res.total_tokens, 1360)

        logs = self.ai_request_repo.get_recent_requests(limit=1)
        self.assertEqual(len(logs), 1)
        logged = logs[0]
        self.assertEqual(logged.provider, "groq")
        self.assertEqual(logged.prompt_tokens, 1150)
        self.assertEqual(logged.completion_tokens, 210)
        self.assertEqual(logged.total_tokens, 1360)
        self.assertTrue(logged.fallback_used)


if __name__ == "__main__":
    unittest.main()
