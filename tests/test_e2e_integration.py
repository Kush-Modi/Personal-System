"""End-to-End integration test for the complete Phase 2 workflow:
Input -> Processing -> Validation -> Pending Item -> Edit -> Save -> Domain Service -> SQLite
"""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.database.migrations import run_migrations
from app.database.repositories.food import FoodRepository
from app.database.repositories.pending_items import PendingItemRepository
from app.domain.models import PendingStatus
from app.domain.validators import validate_payload
from app.input.mock_processor import MockInputProcessor
from app.services.food.service import FoodService
from app.services.pending.service import PendingItemService


class TestEndToEndPhase2Workflow(unittest.TestCase):
    """Verify full end-to-end processing, validation, staging, editing, and final persistence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_e2e.db"
        run_migrations(self.db_path)

        self.pending_repo = PendingItemRepository(self.db_path)
        self.food_repo = FoodRepository(self.db_path)
        self.food_service = FoodService(self.food_repo)
        self.pending_service = PendingItemService(
            pending_repo=self.pending_repo,
            food_service=self.food_service
        )
        self.processor = MockInputProcessor()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_food_workflow_with_edit_and_confirmation(self):
        # 1. User sends mock input
        raw_input = "mock food paneer 400"
        result = self.processor.process_text(raw_input)
        self.assertTrue(result.success)
        self.assertEqual(result.item_type, "FOOD")

        # 2. Validation
        validated = validate_payload(result.item_type, result.payload)
        self.assertEqual(validated.food_name, "paneer")
        self.assertEqual(validated.calories, 400.0)

        # 3. Stage as Pending Item
        pending_item = self.pending_service.create_pending_item(
            item_type=result.item_type,
            structured_payload=result.payload,
            raw_payload=raw_input,
            source=result.source,
            confidence=result.confidence
        )
        self.assertEqual(pending_item.status, PendingStatus.PENDING.value)
        self.assertEqual(pending_item.structured_payload["calories"], 400.0)

        # Verify domain food table is still empty
        today = date.today()
        initial_records = self.food_repo.get_for_date(today)
        self.assertEqual(len(initial_records), 0)

        # 4. User initiates Edit to correct calories to 350
        edited_item = self.pending_service.edit_payload(
            item_id=pending_item.id,
            new_payload={"food_name": "Paneer Tikka", "calories": 350.0}
        )
        self.assertEqual(edited_item.status, PendingStatus.PENDING.value)
        self.assertEqual(edited_item.structured_payload["food_name"], "Paneer Tikka")
        self.assertEqual(edited_item.structured_payload["calories"], 350.0)

        # Verify domain food table is STILL empty after edit (editing must not auto-save)
        records_after_edit = self.food_repo.get_for_date(today)
        self.assertEqual(len(records_after_edit), 0)

        # 5. User clicks Save / Confirm
        confirmed_item, domain_record = self.pending_service.confirm(pending_item.id)
        self.assertEqual(confirmed_item.status, PendingStatus.CONFIRMED.value)

        # 6. Verify SQLite domain table contains the corrected entry
        final_records = self.food_repo.get_for_date(today)
        self.assertEqual(len(final_records), 1)
        self.assertEqual(final_records[0].food_name, "Paneer Tikka")
        self.assertEqual(final_records[0].calories, 350.0)

        # 7. Verify Idempotency on repeated save
        with self.assertRaises(Exception):
            self.pending_service.confirm(pending_item.id)
        self.assertEqual(len(self.food_repo.get_for_date(today)), 1)


if __name__ == "__main__":
    unittest.main()
