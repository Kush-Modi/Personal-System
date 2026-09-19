"""Tests for PendingItem state machine and lifecycle transitions."""

import tempfile
import unittest
from pathlib import Path

from app.core.exceptions import (
    AlreadyProcessedError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from app.database.migrations import run_migrations
from app.database.repositories.food import FoodRepository
from app.database.repositories.pending_items import PendingItemRepository
from app.domain.models import ItemType, PendingStatus
from app.services.food.service import FoodService
from app.services.pending.service import PendingItemService


class TestPendingStateMachine(unittest.TestCase):
    """Test pending item state transitions, idempotency, and validations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pending.db"
        run_migrations(self.db_path)

        self.pending_repo = PendingItemRepository(self.db_path)
        self.food_repo = FoodRepository(self.db_path)
        self.food_service = FoodService(self.food_repo)
        self.pending_service = PendingItemService(
            pending_repo=self.pending_repo,
            food_service=self.food_service
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_transition_pending_to_confirmed(self):
        item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Paneer Roll", "calories": 380}
        )
        self.assertEqual(item.status, PendingStatus.PENDING.value)

        confirmed_item, domain_record = self.pending_service.confirm(item.id)
        self.assertEqual(confirmed_item.status, PendingStatus.CONFIRMED.value)
        self.assertIsNotNone(domain_record)
        self.assertEqual(domain_record.food_name, "Paneer Roll")
        self.assertEqual(domain_record.calories, 380)

        # Verify persisted in food domain table
        food_entries = self.food_repo.get_for_date(self.food_service.get_food_for_date(None)[0][0].created_at if False else None or __import__("datetime").date.today())
        self.assertEqual(len(food_entries), 1)
        self.assertEqual(food_entries[0].food_name, "Paneer Roll")

    def test_transition_pending_to_rejected(self):
        item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Burger", "calories": 500}
        )
        rejected_item = self.pending_service.reject(item.id)
        self.assertEqual(rejected_item.status, PendingStatus.REJECTED.value)

        # Verify nothing was added to food table
        food_entries = self.food_repo.get_for_date(__import__("datetime").date.today())
        self.assertEqual(len(food_entries), 0)

    def test_idempotent_save_double_click_safety(self):
        """Confirming an already confirmed item must raise AlreadyProcessedError and avoid duplicating data."""
        item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Dosa", "calories": 300}
        )
        # First confirmation
        self.pending_service.confirm(item.id)

        # Second confirmation attempt (simulating double click)
        with self.assertRaises(AlreadyProcessedError):
            self.pending_service.confirm(item.id)

        # Verify food table only has 1 record
        food_entries = self.food_repo.get_for_date(__import__("datetime").date.today())
        self.assertEqual(len(food_entries), 1)

    def test_rejected_item_cannot_be_confirmed(self):
        item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Pizza", "calories": 800}
        )
        self.pending_service.reject(item.id)

        with self.assertRaises(AlreadyProcessedError):
            self.pending_service.confirm(item.id)

    def test_expired_item_cannot_be_confirmed(self):
        item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Oats", "calories": 200}
        )
        # Mark expired directly
        self.pending_repo.update_status(item.id, PendingStatus.EXPIRED.value)

        with self.assertRaises(AlreadyProcessedError):
            self.pending_service.confirm(item.id)

    def test_edit_pending_item(self):
        item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Salad", "calories": 150}
        )

        edited = self.pending_service.edit_payload(
            item_id=item.id,
            new_payload={"food_name": "Greek Salad", "calories": 220}
        )
        self.assertEqual(edited.status, PendingStatus.PENDING.value)
        self.assertEqual(edited.structured_payload["food_name"], "Greek Salad")
        self.assertEqual(edited.structured_payload["calories"], 220)

        # Verify nothing was added to final food domain table yet
        food_entries = self.food_repo.get_for_date(__import__("datetime").date.today())
        self.assertEqual(len(food_entries), 0)

        # Now confirm the edited item
        confirmed, domain_rec = self.pending_service.confirm(item.id)
        self.assertEqual(confirmed.status, PendingStatus.CONFIRMED.value)
        self.assertEqual(domain_rec.food_name, "Greek Salad")
        self.assertEqual(domain_rec.calories, 220)

    def test_edit_invalid_payload_fails(self):
        item = self.pending_service.create_pending_item(
            item_type=ItemType.FOOD,
            structured_payload={"food_name": "Salad", "calories": 150}
        )
        with self.assertRaises(ValidationError):
            self.pending_service.edit_payload(item.id, {"food_name": "", "calories": -50})

    def test_missing_pending_item(self):
        with self.assertRaises(NotFoundError):
            self.pending_service.confirm(99999)
        with self.assertRaises(NotFoundError):
            self.pending_service.reject(99999)


if __name__ == "__main__":
    unittest.main()
