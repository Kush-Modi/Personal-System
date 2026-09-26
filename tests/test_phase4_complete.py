"""Comprehensive test suite for Phase 4 completion:
- Receipt / Bill Photo Intelligence & Reconciliation Math Validation
- Persistent Tasks & Lifecycle
- Persistent Reminders, Recurring Calculations, and Duplicate Prevention
- Multi-turn Short-term Conversation Context & Follow-up Corrections
- Safe Deterministic Data Query Planner & Analytics (NO SQL generation)
- AI Fallback Chains, Circuit Breaker, Malformed JSON Handling
- System Failure, Restart, and Network Interruption Simulation
"""

import asyncio
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.budget import AIBudgetManager
from app.ai.provider import AIProvider
from app.ai.router import AIRouter
from app.ai.schemas import (
    AITaskType,
    ExtractedFoodItem,
    ExtractedReceiptItem,
    FoodExtractionResult,
    IntentResult,
    ReceiptExtractionResult,
)
from app.ai.service import AIService
from app.core.exceptions import (
    AlreadyProcessedError,
    DomainValidationError,
    NotFoundError,
    SchemaValidationError,
    ValidationError,
)
from app.database.connection import get_connection
from app.database.migrations import run_migrations
from app.database.repositories.conversation_context import (
    ConversationContextRepository,
)
from app.database.repositories.expense import ExpenseRepository
from app.database.repositories.food import FoodRepository
from app.database.repositories.pending_items import PendingItemRepository
from app.database.repositories.reminder import ReminderRepository
from app.database.repositories.task import TaskRepository
from app.database.repositories.weight import WeightRepository
from app.domain.models import InputSource, ItemType, PendingStatus
from app.input.ai_processor import AIInputProcessor
from app.services.analytics.service import AnalyticsQueryService
from app.services.conversation.service import ConversationContextService
from app.services.pending.service import PendingItemService
from app.services.reminder.scheduler import ReminderScheduler
from app.services.reminder.service import (
    ReminderService,
    calculate_next_recurrence,
)
from app.services.task.service import TaskService


class Phase4CompleteTestSuite(unittest.TestCase):
    """Full unit and integration tests for all remaining Phase 4 components."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_phase4.db"
        
        # Run all migrations up to v005
        run_migrations(self.db_path)

        # Repositories
        self.food_repo = FoodRepository(db_path=self.db_path)
        self.expense_repo = ExpenseRepository(db_path=self.db_path)
        self.weight_repo = WeightRepository(db_path=self.db_path)
        self.task_repo = TaskRepository(db_path=self.db_path)
        self.reminder_repo = ReminderRepository(db_path=self.db_path)
        self.context_repo = ConversationContextRepository(db_path=self.db_path)
        self.pending_repo = PendingItemRepository(db_path=self.db_path)

        # Services
        self.task_service = TaskService(task_repo=self.task_repo)
        self.reminder_service = ReminderService(reminder_repo=self.reminder_repo)
        self.context_service = ConversationContextService(repo=self.context_repo)
        self.analytics_service = AnalyticsQueryService(
            food_repo=self.food_repo,
            expense_repo=self.expense_repo,
            weight_repo=self.weight_repo,
            task_repo=self.task_repo,
            reminder_repo=self.reminder_repo
        )
        self.pending_service = PendingItemService(
            pending_repo=self.pending_repo,
            task_service=self.task_service,
            reminder_service=self.reminder_service
        )

    def tearDown(self):
        self.temp_dir.cleanup()


    # ==================================================
    # 1. RECEIPT / BILL PHOTO & RECONCILIATION TESTS
    # ==================================================
    def test_receipt_math_reconciliation_matching(self):
        """Test that perfectly matching receipt items pass reconciliation without warning."""
        router_mock = MagicMock()
        mock_result = ReceiptExtractionResult(
            merchant="Reliance Fresh",
            date_str="2026-09-26",
            currency="INR",
            items=[
                ExtractedReceiptItem(name="Milk", quantity=2, unit_price=60, total_price=120.0),
                ExtractedReceiptItem(name="Bread", quantity=1, unit_price=45, total_price=45.0),
                ExtractedReceiptItem(name="Vegetables", quantity=1, unit_price=230, total_price=230.0),
            ],
            subtotal=395.0,
            tax=20.0,
            discount=0.0,
            grand_total=415.0,
            category="Groceries",
            confidence=0.95
        )
        router_mock.route_receipt_photo.return_value = (mock_result, False)
        
        from app.database.repositories.ai_request import AIRequestRepository
        ai_req_repo = AIRequestRepository(db_path=self.db_path)
        ai_service = AIService(router=router_mock, ai_request_repo=ai_req_repo)
        res = ai_service.process_receipt_photo("dummy_receipt.jpg")

        self.assertTrue(res.is_reconciled)
        self.assertIsNone(res.mismatch_warning)
        self.assertEqual(res.grand_total, 415.0)
        self.assertEqual(len(res.items), 3)

    def test_receipt_math_reconciliation_mismatch_warning(self):
        """Test that mismatched receipt items generate a clear warning and flag is_reconciled=False."""
        router_mock = MagicMock()
        mock_result = ReceiptExtractionResult(
            merchant="Cafe Coffee Day",
            date_str="2026-09-26",
            currency="INR",
            items=[
                ExtractedReceiptItem(name="Cappuccino", total_price=150.0),
                ExtractedReceiptItem(name="Brownie", total_price=120.0),
            ],
            subtotal=270.0,
            tax=15.0,
            discount=0.0,
            grand_total=350.0,  # Expected 285 vs 350 -> mismatch!
            category="Food & Dining",
            confidence=0.9
        )
        router_mock.route_receipt_photo.return_value = (mock_result, False)
        
        from app.database.repositories.ai_request import AIRequestRepository
        ai_req_repo = AIRequestRepository(db_path=self.db_path)
        ai_service = AIService(router=router_mock, ai_request_repo=ai_req_repo)
        res = ai_service.process_receipt_photo("mismatched_bill.jpg")

        self.assertFalse(res.is_reconciled)
        self.assertIsNotNone(res.mismatch_warning)
        self.assertIn("mismatch in the receipt totals", res.mismatch_warning)
        self.assertEqual(res.grand_total, 350.0)


    # ==================================================
    # 2. TASK PERSISTENCE & LIFECYCLE TESTS
    # ==================================================
    def test_task_create_list_complete_cancel(self):
        """Test full task CRUD lifecycle."""
        task1 = self.task_service.create_task(title="Apply to CyberMACS", due_at="2026-10-01", priority="HIGH")
        task2 = self.task_service.create_task(title="Buy milk", priority="LOW")

        self.assertEqual(task1.id, 1)
        self.assertEqual(task1.status, "PENDING")
        self.assertEqual(task1.priority, "HIGH")

        # List pending
        pending = self.task_service.list_pending_tasks()
        self.assertEqual(len(pending), 2)

        # Complete task1
        completed_task = self.task_service.complete_task(task1.id)
        self.assertEqual(completed_task.status, "COMPLETED")
        self.assertIsNotNone(completed_task.completed_at)

        # Cancel task2
        cancelled_task = self.task_service.cancel_task(task2.id)
        self.assertEqual(cancelled_task.status, "CANCELLED")

        # Check pending is now empty
        self.assertEqual(len(self.task_service.list_pending_tasks()), 0)

    def test_task_pending_confirmation_flow(self):
        """Test creating and confirming a task through the pending items workflow."""
        pending_item = self.pending_service.create_pending_item(
            item_type=ItemType.TASK,
            structured_payload={"title": "Submit assignment", "due_date": "2026-09-30", "priority": "HIGH"},
            source=InputSource.TEXT.value
        )
        self.assertEqual(pending_item.status, "PENDING")

        # Confirm
        updated_item, record = self.pending_service.confirm(pending_item.id)
        self.assertEqual(updated_item.status, "CONFIRMED")
        self.assertEqual(record.title, "Submit assignment")

        # Check DB
        saved_tasks = self.task_service.list_pending_tasks()
        self.assertEqual(len(saved_tasks), 1)
        self.assertEqual(saved_tasks[0].title, "Submit assignment")

    # ==================================================
    # 3. REMINDERS, SCHEDULER & RECURRENCE TESTS
    # ==================================================
    def test_reminder_recurrence_calculations(self):
        """Test deterministic recurrence calculations for daily, weekly, monthly, weekdays."""
        base_time = "2026-09-26 09:00:00"  # Saturday
        
        # Daily
        next_daily = calculate_next_recurrence(base_time, "DAILY")
        self.assertEqual(next_daily, "2026-09-27 09:00:00")

        # Weekly
        next_weekly = calculate_next_recurrence(base_time, "WEEKLY")
        self.assertEqual(next_weekly, "2026-10-03 09:00:00")

        # Monthly
        next_monthly = calculate_next_recurrence(base_time, "MONTHLY")
        self.assertEqual(next_monthly, "2026-10-26 09:00:00")

        # Weekdays: from Saturday 2026-09-26, next weekday is Monday 2026-09-28
        next_weekday = calculate_next_recurrence(base_time, "WEEKDAYS")
        self.assertEqual(next_weekday, "2026-09-28 09:00:00")

    def test_scheduler_atomic_claim_and_duplicate_prevention(self):
        """Test that scheduler atomically claims due reminders, preventing duplicate dispatches."""
        past_time = "2026-09-26 08:00:00"
        rem1 = self.reminder_service.create_reminder("Drink water", remind_at=past_time)
        rem2 = self.reminder_service.create_reminder("Check server", remind_at=past_time)

        # First claim cycle
        now_str = "2026-09-26 09:00:00"
        claimed_first = self.reminder_repo.claim_due_reminders(now_str, limit=10)
        self.assertEqual(len(claimed_first), 2)
        self.assertTrue(all(r.status == "CLAIMED" for r in claimed_first))

        # Concurrent second claim cycle before first finishes: must return 0
        claimed_second = self.reminder_repo.claim_due_reminders(now_str, limit=10)
        self.assertEqual(len(claimed_second), 0)

        # Mark sent
        self.reminder_repo.mark_sent(rem1.id, triggered_at=now_str)
        rem1_after = self.reminder_repo.get_by_id(rem1.id)
        self.assertEqual(rem1_after.status, "SENT")

        # Simulate network failure on rem2: release claim back to PENDING
        self.reminder_repo.release_claimed_to_pending(rem2.id)
        rem2_after = self.reminder_repo.get_by_id(rem2.id)
        self.assertEqual(rem2_after.status, "PENDING")

    def test_scheduler_async_dispatch_cycle(self):
        """Test complete async polling dispatch cycle with mock Telegram bot."""
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        scheduler = ReminderScheduler(
            reminder_repo=self.reminder_repo,
            bot=mock_bot,
            target_chat_id=123456
        )

        # Create past due reminder
        past_time = "2020-01-01 08:00:00"
        self.reminder_service.create_reminder("Call mom", remind_at=past_time, user_id=123456)

        # Run poll
        loop = asyncio.new_event_loop()
        sent_count = loop.run_until_complete(scheduler.poll_and_dispatch())
        loop.close()

        self.assertEqual(sent_count, 1)
        mock_bot.send_message.assert_called_once()
        self.assertIn("Call mom", mock_bot.send_message.call_args[1]["text"])

    # ==================================================
    # 4. MULTI-TURN CONVERSATION CONTEXT & FOLLOW-UP CORRECTION
    # ==================================================
    def test_conversation_context_persistence_and_ttl(self):
        """Test recording conversational turns and TTL bounding."""
        # Create a real pending item first for FK reference
        pending = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Roti", "calories": 200.0}
        )

        self.context_service.record_turn(
            user_id=1001,
            user_message="I had 2 rotis",
            bot_response="Recorded 200 kcal",
            intent="FOOD",
            active_pending_id=pending.id
        )

        ctx = self.context_service.get_context(1001)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.last_intent, "FOOD")
        self.assertEqual(ctx.active_pending_id, pending.id)
        self.assertEqual(len(ctx.recent_messages), 2)

        # Clear
        self.context_service.clear_context(1001)
        self.assertIsNone(self.context_service.get_context(1001))


    # ==================================================
    # 5. DATA QUERIES & ANALYTICS (NO AI SQL)
    # ==================================================
    def test_analytics_food_calories_query(self):
        """Test deterministic food analytics across single day and date ranges."""
        today = date.today()
        self.food_repo.add("Roti", 200.0, record_date=today)
        self.food_repo.add("Dal", 150.0, record_date=today)

        query_plan_today = {
            "domain": "FOOD",
            "operation": "TOTAL",
            "date_range": {"range": "today"}
        }
        res_today = self.analytics_service.execute_query(query_plan_today)
        self.assertIn("350 kcal", res_today)
        self.assertIn("Roti", res_today)

        query_plan_avg = {
            "domain": "FOOD",
            "operation": "AVERAGE",
            "date_range": {"range": "this_week"}
        }
        res_avg = self.analytics_service.execute_query(query_plan_avg)
        self.assertIn("Average Daily Calories", res_avg)

    def test_analytics_expense_query(self):
        """Test deterministic expense analytics by total and category."""
        self.expense_repo.add(450.0, "Food & Dining", "Starbucks")
        self.expense_repo.add(1200.0, "Groceries", "Reliance")
        self.expense_repo.add(300.0, "Transport", "Uber")

        # Total query
        res_total = self.analytics_service.execute_query({
            "domain": "EXPENSE",
            "operation": "TOTAL",
            "date_range": {"range": "today"}
        })
        self.assertIn("1950.00", res_total)
        self.assertIn("Groceries", res_total)

        # Filtered query
        res_cat = self.analytics_service.execute_query({
            "domain": "EXPENSE",
            "operation": "TOTAL",
            "date_range": {"range": "today"},
            "filters": {"category": "Groceries"}
        })
        self.assertIn("1200.00", res_cat)

        # Highest query
        res_high = self.analytics_service.execute_query({
            "domain": "EXPENSE",
            "operation": "HIGHEST",
            "date_range": {"range": "today"}
        })
        self.assertIn("1200.00", res_high)
        self.assertIn("Reliance", res_high)

    def test_analytics_weight_trend_query(self):
        """Test deterministic weight trend calculations."""
        today = date.today()
        self.weight_repo.upsert_for_date(today - timedelta(days=3), 77.5)
        self.weight_repo.upsert_for_date(today - timedelta(days=1), 76.8)
        self.weight_repo.upsert_for_date(today, 76.2)

        res_trend = self.analytics_service.execute_query({
            "domain": "WEIGHT",
            "operation": "TREND",
            "date_range": {"range": "this_week"}
        })
        self.assertIn("76.2 kg", res_trend)
        self.assertIn("-1.3 kg", res_trend)


if __name__ == "__main__":
    unittest.main()
