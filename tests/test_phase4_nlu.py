"""Comprehensive test suite for Phase 4.1–4.4: Unified Natural Language Understanding,
Food, Expense, Weight tracking, Multi-domain Routing, and Edge Cases.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.ai.budget import AIBudgetManager
from app.ai.provider import AIProvider
from app.ai.router import AIRouter
from app.ai.schemas import (
    AITaskType,
    ExtractedFoodItem,
    FoodExtractionResult,
    IntentResult,
    parse_intent_result,
)
from app.ai.service import AIService
from app.core.exceptions import DomainValidationError, SchemaValidationError, ValidationError
from app.database.migrations import run_migrations
from app.database.repositories.ai_provider_health import AIProviderHealthRepository
from app.database.repositories.ai_request import AIRequestRepository
from app.database.repositories.expense import ExpenseRepository
from app.database.repositories.food import FoodRepository
from app.database.repositories.food_memory import FoodMemoryRepository
from app.database.repositories.pending_items import PendingItemRepository
from app.database.repositories.weight import WeightRepository
from app.domain.models import InputSource, ItemType, PendingStatus
from app.domain.validators import (
    validate_expense_domain,
    validate_expense_schema,
    validate_food_domain,
    validate_food_schema,
    validate_payload,
    validate_weight_domain,
    validate_weight_schema,
)
from app.input.ai_processor import AIInputProcessor
from app.services.finance.service import FinanceService
from app.services.food.service import FoodService
from app.services.food_memory.service import FoodMemoryService
from app.services.pending.service import PendingItemService
from app.services.weight.service import WeightService
from app.telegram.renderers import (
    render_edit_prompt,
    render_pending_preview,
    render_saved_confirmation,
)


class MockNLUProvider(AIProvider):
    """Configurable mock AI provider for testing multi-domain intent routing."""

    def __init__(self, name: str = "gemini", canned_results: dict = None):
        self._name = name
        self.canned_results = canned_results or {}
        self.call_count = 0

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
        return FoodExtractionResult(
            items=[ExtractedFoodItem(food_name="Paneer Butter Masala", estimated_calories=400.0)],
            provider=self._name,
            model="test-vision",
        )

    def extract_food_from_text(self, text, memory_context=""):
        return FoodExtractionResult(
            items=[ExtractedFoodItem(food_name="Roti", estimated_calories=100.0)],
            provider=self._name,
            model="test-text",
        )

    def extract_receipt_from_image(self, image_path):
        raise NotImplementedError()

    def extract_intent_action(self, text: str, current_date: str = None, memory_context: str = "") -> IntentResult:
        self.call_count += 1
        # Match from canned results dictionary
        if text in self.canned_results:
            res = self.canned_results[text]
            res.provider = self._name
            res.model = "test-nlu-model"
            return res

        # Default fallback
        return IntentResult(
            intent="OTHER",
            confidence=0.5,
            response_mode="CLARIFICATION",
            chat_response="Could you please specify what you would like to log?",
            provider=self._name,
            model="test-nlu-model",
        )


class TestPhase4NLU(unittest.TestCase):
    """Test suite covering Phase 4.1 to 4.4 implementation requirements."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_phase4.db"
        run_migrations(self.db_path)

        # Repositories
        self.pending_repo = PendingItemRepository(db_path=self.db_path)
        self.food_repo = FoodRepository(db_path=self.db_path)
        self.expense_repo = ExpenseRepository(db_path=self.db_path)
        self.weight_repo = WeightRepository(db_path=self.db_path)
        self.food_mem_repo = FoodMemoryRepository(db_path=self.db_path)
        self.ai_req_repo = AIRequestRepository(db_path=self.db_path)
        self.health_repo = AIProviderHealthRepository(db_path=self.db_path)

        # Services
        self.food_service = FoodService(repository=self.food_repo)
        self.finance_service = FinanceService(repository=self.expense_repo)
        self.weight_service = WeightService(weight_repository=self.weight_repo, food_repository=self.food_repo)
        self.food_memory_service = FoodMemoryService(repository=self.food_mem_repo)

        self.pending_service = PendingItemService(
            pending_repo=self.pending_repo,
            food_service=self.food_service,
            finance_service=self.finance_service,
            weight_service=self.weight_service,
            food_memory_service=self.food_memory_service,
        )


        # Set up canned NLU responses
        self.canned = {
            # 1. FOOD CASES
            "I had 2 rotis and 1 bowl of dal": IntentResult(
                intent="FOOD",
                confidence=0.96,
                response_mode="ACTION",
                action={
                    "items": [
                        {"name": "Roti", "quantity": 2.0, "unit": "piece", "estimated_calories": 200.0},
                        {"name": "Dal", "quantity": 1.0, "unit": "bowl", "estimated_calories": 180.0},
                    ],
                    "total_calories": 380.0,
                    "meal_type": "Lunch",
                },
                requires_confirmation=True,
            ),
            "Had paneer tikka for lunch": IntentResult(
                intent="FOOD",
                confidence=0.95,
                response_mode="ACTION",
                action={
                    "items": [
                        {"name": "Paneer Tikka", "quantity": 1.0, "unit": "plate", "estimated_calories": 350.0},
                    ],
                    "total_calories": 350.0,
                    "meal_type": "Lunch",
                },
                requires_confirmation=True,
            ),
            "I ate 3 bananas": IntentResult(
                intent="FOOD",
                confidence=0.98,
                response_mode="ACTION",
                action={
                    "items": [
                        {"name": "Banana", "quantity": 3.0, "unit": "piece", "estimated_calories": 270.0},
                    ],
                    "total_calories": 270.0,
                    "meal_type": "Snack",
                },
                requires_confirmation=True,
            ),
            "I had 60g oats with protein milk": IntentResult(
                intent="FOOD",
                confidence=0.94,
                response_mode="ACTION",
                action={
                    "items": [
                        {"name": "Oats", "quantity": 60.0, "unit": "g", "estimated_calories": 230.0},
                        {"name": "Protein Milk", "quantity": 1.0, "unit": "cup", "estimated_calories": 150.0},
                    ],
                    "total_calories": 380.0,
                    "meal_type": "Breakfast",
                },
                requires_confirmation=True,
            ),
            "2 rotis, sabzi and dahi": IntentResult(
                intent="FOOD",
                confidence=0.92,
                response_mode="ACTION",
                action={
                    "items": [
                        {"name": "Roti", "quantity": 2.0, "unit": "piece", "estimated_calories": 200.0},
                        {"name": "Sabzi", "quantity": 1.0, "unit": "bowl", "estimated_calories": 150.0},
                        {"name": "Dahi", "quantity": 1.0, "unit": "cup", "estimated_calories": 100.0},
                    ],
                    "total_calories": 450.0,
                    "meal_type": "Dinner",
                },
                requires_confirmation=True,
            ),
            "Add 500 calories for dinner": IntentResult(
                intent="FOOD",
                confidence=0.99,
                response_mode="ACTION",
                action={
                    "items": [
                        {"name": "Dinner Meal", "quantity": 1.0, "unit": "serving", "estimated_calories": 500.0},
                    ],
                    "total_calories": 500.0,
                    "meal_type": "Dinner",
                },
                requires_confirmation=True,
            ),

            # 2. EXPENSE CASES
            "I spent ₹450 at Starbucks": IntentResult(
                intent="EXPENSE",
                confidence=0.98,
                response_mode="ACTION",
                action={
                    "amount": 450.0,
                    "currency": "INR",
                    "merchant": "Starbucks",
                    "category": "Food & Dining",
                    "date": None,
                    "note": "Coffee",
                },
                requires_confirmation=True,
            ),
            "Paid 1200 for groceries": IntentResult(
                intent="EXPENSE",
                confidence=0.97,
                response_mode="ACTION",
                action={
                    "amount": 1200.0,
                    "currency": "INR",
                    "category": "Groceries",
                    "date": None,
                },
                requires_confirmation=True,
            ),
            "Spent 300 on Uber": IntentResult(
                intent="EXPENSE",
                confidence=0.97,
                response_mode="ACTION",
                action={
                    "amount": 300.0,
                    "currency": "INR",
                    "merchant": "Uber",
                    "category": "Transport",
                },
                requires_confirmation=True,
            ),
            "Bought a shirt for ₹1800": IntentResult(
                intent="EXPENSE",
                confidence=0.96,
                response_mode="ACTION",
                action={
                    "amount": 1800.0,
                    "currency": "INR",
                    "category": "Shopping",
                    "note": "Shirt",
                },
                requires_confirmation=True,
            ),
            "₹80 chai and samosa": IntentResult(
                intent="EXPENSE",
                confidence=0.93,
                response_mode="ACTION",
                action={
                    "amount": 80.0,
                    "currency": "INR",
                    "category": "Food & Dining",
                    "note": "Chai and samosa",
                },
                requires_confirmation=True,
            ),
            "Spent 500 today": IntentResult(
                intent="EXPENSE",
                confidence=0.90,
                response_mode="ACTION",
                action={
                    "amount": 500.0,
                    "currency": "INR",
                    "category": "Other",
                },
                requires_confirmation=True,
            ),

            # 3. WEIGHT CASES
            "I'm 76.2 kg today": IntentResult(
                intent="WEIGHT",
                confidence=0.99,
                response_mode="ACTION",
                action={
                    "weight_kg": 76.2,
                    "date": None,
                    "unit_original": "kg",
                },
                requires_confirmation=False,
            ),
            "My weight is 75.8": IntentResult(
                intent="WEIGHT",
                confidence=0.98,
                response_mode="ACTION",
                action={
                    "weight_kg": 75.8,
                    "date": None,
                    "unit_original": "kg",
                },
                requires_confirmation=False,
            ),
            "Weight 75.6 kg": IntentResult(
                intent="WEIGHT",
                confidence=0.99,
                response_mode="ACTION",
                action={
                    "weight_kg": 75.6,
                    "date": None,
                    "unit_original": "kg",
                },
                requires_confirmation=False,
            ),

            # 4. AMBIGUOUS CASES
            "I spent some money": IntentResult(
                intent="OTHER",
                confidence=0.4,
                response_mode="CLARIFICATION",
                chat_response="How much money did you spend and what was it for?",
            ),
            "₹500": IntentResult(
                intent="OTHER",
                confidence=0.5,
                response_mode="CLARIFICATION",
                chat_response="Did you spend ₹500? What was the category or merchant?",
            ),
            "I'm 76": IntentResult(
                intent="OTHER",
                confidence=0.6,
                response_mode="CLARIFICATION",
                chat_response="Did you want to log your weight as 76.0 kg?",
            ),
            "Remind me about this": IntentResult(
                intent="OTHER",
                confidence=0.5,
                response_mode="CLARIFICATION",
                chat_response="What would you like me to remind you about, and at what time?",
            ),
            "Had something heavy": IntentResult(
                intent="OTHER",
                confidence=0.4,
                response_mode="CLARIFICATION",
                chat_response="What did you eat? Please describe the dish or items.",
            ),

            # 5. GENERAL CHAT
            "What should I focus on today?": IntentResult(
                intent="GENERAL_CHAT",
                confidence=0.95,
                response_mode="CHAT",
                chat_response="Prioritize your top 1-2 critical goals for the day and block distraction-free time.",
            ),
            "Explain this to me": IntentResult(
                intent="GENERAL_CHAT",
                confidence=0.92,
                response_mode="CHAT",
                chat_response="I'd be glad to explain! What topic would you like to explore?",
            ),

            # 6. DATA QUERY
            "How many calories did I eat yesterday?": IntentResult(
                intent="DATA_QUERY",
                confidence=0.96,
                response_mode="QUERY",
                chat_response="Historical calorie queries are arriving in Phase 4.7. You can check /summary for today's log.",
            ),
            "How much did I spend this month?": IntentResult(
                intent="DATA_QUERY",
                confidence=0.97,
                response_mode="QUERY",
                chat_response="Monthly financial summary is available via /monthly.",
            ),
            "What was my weight last week?": IntentResult(
                intent="DATA_QUERY",
                confidence=0.96,
                response_mode="QUERY",
                chat_response="You can view your weekly weight progress using /weight history.",
            ),

            # 7. HINDI / HINGLISH
            "Aaj maine do roti aur dal khayi": IntentResult(
                intent="FOOD",
                confidence=0.94,
                response_mode="ACTION",
                action={
                    "items": [
                        {"name": "Roti", "quantity": 2.0, "unit": "piece", "estimated_calories": 200.0},
                        {"name": "Dal", "quantity": 1.0, "unit": "bowl", "estimated_calories": 180.0},
                    ],
                    "total_calories": 380.0,
                    "meal_type": "Lunch",
                },
                requires_confirmation=True,
            ),
            "Aaj ₹500 groceries pe spend kiya": IntentResult(
                intent="EXPENSE",
                confidence=0.96,
                response_mode="ACTION",
                action={
                    "amount": 500.0,
                    "currency": "INR",
                    "category": "Groceries",
                },
                requires_confirmation=True,
            ),
            "Mera weight aaj 76.2 hai": IntentResult(
                intent="WEIGHT",
                confidence=0.97,
                response_mode="ACTION",
                action={
                    "weight_kg": 76.2,
                    "date": None,
                    "unit_original": "kg",
                },
                requires_confirmation=False,
            ),
        }

        self.mock_provider = MockNLUProvider("gemini", canned_results=self.canned)
        self.router = AIRouter(
            providers={"gemini": self.mock_provider},
            health_repo=self.health_repo,
        )
        self.budget_mgr = AIBudgetManager(ai_request_repo=self.ai_req_repo)
        self.ai_service = AIService(
            router=self.router,
            budget_manager=self.budget_mgr,
            food_memory_service=self.food_memory_service,
            ai_request_repo=self.ai_req_repo,
            pending_repo=self.pending_repo,
        )
        self.input_processor = AIInputProcessor(ai_service=self.ai_service)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ==================================================
    # PHASE 4.1: UNIFIED INTENT SCHEMA & PARSING
    # ==================================================
    def test_parse_intent_result_robustness(self):
        """Test parse_intent_result handles diverse nested and raw LLM dictionaries."""
        raw_dict = {
            "intent": "FOOD",
            "confidence": 0.91,
            "response_mode": "ACTION",
            "action": {
                "food": {
                    "items": [{"name": "Dosa", "estimated_calories": 300}],
                    "total_calories": 300,
                }
            },
            "requires_confirmation": True,
        }
        res = parse_intent_result(raw_dict)
        self.assertEqual(res.intent, "FOOD")
        self.assertEqual(res.response_mode, "ACTION")
        self.assertEqual(res.action.get("total_calories"), 300)
        self.assertTrue(res.requires_confirmation)

    def test_parse_intent_result_malformed(self):
        """Test parse_intent_result handles malformed input gracefully."""
        res = parse_intent_result("not a dict")
        self.assertEqual(res.intent, "OTHER")
        self.assertEqual(res.response_mode, "CLARIFICATION")

    # ==================================================
    # PHASE 4.2: NATURAL-LANGUAGE FOOD TRACKING
    # ==================================================
    def test_food_natural_language_pipeline(self):
        """Test natural language food processing and confirmation workflow."""
        text = "I had 2 rotis and 1 bowl of dal"
        proc_res = self.input_processor.process_text(text)

        self.assertTrue(proc_res.success)
        self.assertEqual(proc_res.item_type, ItemType.FOOD.value)
        self.assertEqual(proc_res.payload["calories"], 380.0)
        self.assertIn("Roti", proc_res.payload["food_name"])
        self.assertIn("Dal", proc_res.payload["food_name"])
        self.assertTrue(proc_res.requires_confirmation)

        # Create pending item
        pending = self.pending_service.create_pending_item(
            item_type=proc_res.item_type,
            structured_payload=proc_res.payload,
            raw_payload=proc_res.raw_text,
            source=InputSource.TEXT.value,
            confidence=proc_res.confidence,
        )
        self.assertEqual(pending.status, PendingStatus.PENDING.value)

        # Confirm pending item
        confirmed_item, domain_rec = self.pending_service.confirm(pending.id)
        self.assertEqual(confirmed_item.status, PendingStatus.CONFIRMED.value)
        self.assertEqual(domain_rec.calories, 380.0)

        # Verify persisted to food repository
        from datetime import date
        today_foods = self.food_repo.get_for_date(date.today())
        self.assertEqual(len(today_foods), 1)
        self.assertEqual(today_foods[0].calories, 380.0)

        # Verify learned into Food Memory
        mem = self.food_mem_repo.find_by_name_or_alias("Roti, Dal")
        self.assertIsNotNone(mem)
        self.assertEqual(mem.default_calories, 380.0)

    def test_food_rejection_workflow(self):
        """Test user rejecting a pending food item."""
        from datetime import date
        proc_res = self.input_processor.process_text("I ate 3 bananas")
        pending = self.pending_service.create_pending_item(
            item_type=proc_res.item_type,
            structured_payload=proc_res.payload,
        )
        rejected = self.pending_service.reject(pending.id)
        self.assertEqual(rejected.status, PendingStatus.REJECTED.value)
        self.assertEqual(len(self.food_repo.get_for_date(date.today())), 0)

    def test_food_edit_workflow(self):
        """Test editing a pending food item before confirmation."""
        proc_res = self.input_processor.process_text("Had paneer tikka for lunch")
        pending = self.pending_service.create_pending_item(
            item_type=proc_res.item_type,
            structured_payload=proc_res.payload,
        )
        # Edit calories
        updated = self.pending_service.edit_payload(pending.id, {"food_name": "Paneer Tikka Double", "calories": 500.0})
        self.assertEqual(updated.structured_payload["calories"], 500.0)

        # Confirm edited
        _, rec = self.pending_service.confirm(updated.id)
        self.assertEqual(rec.calories, 500.0)

    # ==================================================
    # PHASE 4.3: MONEY / EXPENSE TRACKING
    # ==================================================
    def test_expense_natural_language_pipeline(self):
        """Test natural language expense tracking and persistence."""
        from datetime import date
        text = "I spent ₹450 at Starbucks"
        proc_res = self.input_processor.process_text(text)

        self.assertTrue(proc_res.success)
        self.assertEqual(proc_res.item_type, ItemType.EXPENSE.value)
        self.assertEqual(proc_res.payload["amount"], 450.0)
        self.assertEqual(proc_res.payload["category"], "Food & Dining")
        self.assertEqual(proc_res.payload["merchant"], "Starbucks")
        self.assertTrue(proc_res.requires_confirmation)

        # Staging
        pending = self.pending_service.create_pending_item(
            item_type=proc_res.item_type,
            structured_payload=proc_res.payload,
        )
        confirmed, domain_rec = self.pending_service.confirm(pending.id)
        self.assertEqual(confirmed.status, PendingStatus.CONFIRMED.value)

        # Verify expense repo persistence
        expenses = self.expense_repo.get_for_date(date.today())
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0].amount, 450.0)
        self.assertEqual(expenses[0].category, "Food & Dining")

    def test_expense_rejection(self):
        """Test rejecting an expense item."""
        from datetime import date
        proc_res = self.input_processor.process_text("Spent 300 on Uber")
        pending = self.pending_service.create_pending_item(
            item_type=proc_res.item_type,
            structured_payload=proc_res.payload,
        )
        self.pending_service.reject(pending.id)
        self.assertEqual(len(self.expense_repo.get_for_date(date.today())), 0)

    # ==================================================
    # PHASE 4.4: WEIGHT TRACKING & DUPLICATE BEHAVIOR
    # ==================================================
    def test_weight_direct_logging(self):
        """Test deterministic weight logging directly persists to database."""
        from datetime import date
        text = "I'm 76.2 kg today"
        proc_res = self.input_processor.process_text(text)

        self.assertTrue(proc_res.success)
        self.assertEqual(proc_res.item_type, ItemType.WEIGHT.value)
        self.assertEqual(proc_res.payload["weight_kg"], 76.2)
        self.assertFalse(proc_res.requires_confirmation)

        # Record via weight service
        is_updated, recorded_weight = self.weight_service.record_weight(weight_kg=proc_res.payload["weight_kg"])
        self.assertEqual(recorded_weight, 76.2)

        # Verify in repository
        latest = self.weight_repo.get_for_date(date.today())
        self.assertEqual(latest, 76.2)

    def test_weight_duplicate_same_day_overwrites(self):
        """Test recording new weight on the same day updates existing record rather than failing."""
        # First entry
        self.weight_service.record_weight(weight_kg=76.2, date="2026-09-26")
        entries_1 = self.weight_repo.get_recent(limit=10)
        self.assertEqual(len(entries_1), 1)
        self.assertEqual(entries_1[0][0], 76.2)

        # Second entry on same day
        self.weight_service.record_weight(weight_kg=75.8, date="2026-09-26")
        entries_2 = self.weight_repo.get_recent(limit=10)
        # Should still have 1 entry with updated weight
        self.assertEqual(len(entries_2), 1)
        self.assertEqual(entries_2[0][0], 75.8)


    def test_weight_validation_bounds(self):
        """Test domain validation bounds on weight (must be > 0 and <= 500)."""
        with self.assertRaises(ValidationError):
            validate_payload(ItemType.WEIGHT, {"weight_kg": -5.0})
        with self.assertRaises(ValidationError):
            validate_payload(ItemType.WEIGHT, {"weight_kg": 600.0})
        with self.assertRaises(ValidationError):
            validate_payload(ItemType.WEIGHT, {"weight_kg": 5.0})  # below 10 kg warning

    # ==================================================
    # CHAT, QUERY & AMBIGUOUS HANDLING
    # ==================================================
    def test_general_chat_routing(self):
        """Test general conversational messages are routed as CHAT without domain action."""
        proc_res = self.input_processor.process_text("What should I focus on today?")
        self.assertTrue(proc_res.success)
        self.assertEqual(proc_res.item_type, ItemType.GENERAL_CHAT.value)
        self.assertEqual(proc_res.response_mode, "CHAT")
        self.assertIn("Prioritize", proc_res.payload["reply"])

    def test_data_query_routing(self):
        """Test data questions are routed as QUERY and not executed as actions."""
        proc_res = self.input_processor.process_text("How many calories did I eat yesterday?")
        self.assertTrue(proc_res.success)
        self.assertEqual(proc_res.item_type, ItemType.DATA_QUERY.value)
        self.assertEqual(proc_res.response_mode, "QUERY")

    def test_ambiguous_clarification_routing(self):
        """Test vague or missing information triggers polite CLARIFICATION."""
        proc_res = self.input_processor.process_text("I spent some money")
        self.assertTrue(proc_res.success)
        self.assertEqual(proc_res.response_mode, "CLARIFICATION")
        self.assertIn("spend", proc_res.payload["reply"].lower())

    # ==================================================
    # HINDI / HINGLISH UNDERSTANDING
    # ==================================================
    def test_hinglish_food(self):
        """Test Hinglish food input correctly creates food item."""
        proc_res = self.input_processor.process_text("Aaj maine do roti aur dal khayi")
        self.assertEqual(proc_res.item_type, ItemType.FOOD.value)
        self.assertEqual(proc_res.payload["calories"], 380.0)

    def test_hinglish_expense(self):
        """Test Hinglish expense input correctly extracts expense."""
        proc_res = self.input_processor.process_text("Aaj ₹500 groceries pe spend kiya")
        self.assertEqual(proc_res.item_type, ItemType.EXPENSE.value)
        self.assertEqual(proc_res.payload["amount"], 500.0)
        self.assertEqual(proc_res.payload["category"], "Groceries")

    def test_hinglish_weight(self):
        """Test Hinglish weight input correctly extracts weight."""
        proc_res = self.input_processor.process_text("Mera weight aaj 76.2 hai")
        self.assertEqual(proc_res.item_type, ItemType.WEIGHT.value)
        self.assertEqual(proc_res.payload["weight_kg"], 76.2)

    # ==================================================
    # TELEMETRY & BUDGET ENFORCEMENT
    # ==================================================
    def test_telemetry_logging_on_intent_action(self):
        """Test that every NLU execution logs structured telemetry."""
        initial_count = len(self.ai_req_repo.get_recent_requests(limit=50))
        self.input_processor.process_text("I spent ₹450 at Starbucks")
        new_count = len(self.ai_req_repo.get_recent_requests(limit=50))
        self.assertEqual(new_count, initial_count + 1)
        recent = self.ai_req_repo.get_recent_requests(limit=1)[0]
        self.assertEqual(recent.status, "SUCCESS")

    # ==================================================
    # RENDERERS VERIFICATION
    # ==================================================
    def test_renderers_for_all_item_types(self):
        """Test Telegram Markdown renderers for FOOD, EXPENSE, and WEIGHT."""
        food_item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Roti", "calories": 100.0},
        )
        expense_item = self.pending_service.create_pending_item(
            item_type=ItemType.EXPENSE,
            structured_payload={"amount": 450.0, "category": "Food & Dining", "merchant": "Starbucks"},
        )
        weight_item = self.pending_service.create_pending_item(
            item_type=ItemType.WEIGHT,
            structured_payload={"weight_kg": 76.2, "date": "2026-09-26"},
        )

        # Preview rendering
        self.assertIn("Roti", render_pending_preview(food_item))
        self.assertIn("450.00", render_pending_preview(expense_item))
        self.assertIn("76.2 kg", render_pending_preview(weight_item))

        # Confirmation rendering
        self.assertIn("Food Log", render_saved_confirmation(food_item, {}))
        self.assertIn("Expenses", render_saved_confirmation(expense_item, {}))
        self.assertIn("Weight Log", render_saved_confirmation(weight_item, {}))

        # Edit prompt rendering
        self.assertIn("Editing Food", render_edit_prompt(food_item))
        self.assertIn("Editing Expense", render_edit_prompt(expense_item))
        self.assertIn("Editing Weight", render_edit_prompt(weight_item))


if __name__ == "__main__":
    unittest.main()
