"""Tests for SQLite database repositories."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.database.migrations import run_migrations
from app.database.repositories.expense import ExpenseRepository
from app.database.repositories.food import FoodRepository
from app.database.repositories.pending_items import PendingItemRepository
from app.database.repositories.weight import WeightRepository


class TestRepositories(unittest.TestCase):
    """Test repository CRUD operations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_repo.db"
        run_migrations(self.db_path)

        self.food_repo = FoodRepository(self.db_path)
        self.weight_repo = WeightRepository(self.db_path)
        self.expense_repo = ExpenseRepository(self.db_path)
        self.pending_repo = PendingItemRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_food_repository(self):
        today = date.today()
        # Add
        food_id = self.food_repo.add("Apple", 95.0)
        self.assertGreater(food_id, 0)

        # Get by id
        record = self.food_repo.get_by_id(food_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.food_name, "Apple")
        self.assertEqual(record.calories, 95.0)

        # Get for date
        records = self.food_repo.get_for_date(today)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, food_id)

        # Update
        updated = self.food_repo.update(food_id, "Large Apple", 110.0)
        self.assertTrue(updated)
        updated_rec = self.food_repo.get_by_id(food_id)
        self.assertEqual(updated_rec.food_name, "Large Apple")
        self.assertEqual(updated_rec.calories, 110.0)

        # Date stats
        count, total = self.food_repo.get_date_stats(today)
        self.assertEqual(count, 1)
        self.assertEqual(total, 110.0)

        # Delete
        deleted = self.food_repo.delete(food_id)
        self.assertTrue(deleted)
        self.assertIsNone(self.food_repo.get_by_id(food_id))

    def test_weight_repository(self):
        today = date.today()
        # Insert
        is_updated, record_id = self.weight_repo.upsert_for_date(today, 75.0)
        self.assertFalse(is_updated)
        self.assertGreater(record_id, 0)

        # Query
        w = self.weight_repo.get_for_date(today)
        self.assertEqual(w, 75.0)

        # Update
        is_updated, _ = self.weight_repo.upsert_for_date(today, 74.5)
        self.assertTrue(is_updated)
        self.assertEqual(self.weight_repo.get_for_date(today), 74.5)

        # Recent history
        recent = self.weight_repo.get_recent(5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0][0], 74.5)

        # Delete
        deleted = self.weight_repo.delete_for_date(today)
        self.assertTrue(deleted)
        self.assertIsNone(self.weight_repo.get_for_date(today))

    def test_expense_repository(self):
        today = date.today()
        exp_id = self.expense_repo.add(250.0, "Food", "Lunch with team")
        self.assertGreater(exp_id, 0)

        expenses = self.expense_repo.get_for_date(today)
        self.assertEqual(len(expenses), 1)
        self.assertEqual(expenses[0].amount, 250.0)
        self.assertEqual(expenses[0].category, "Food")
        self.assertEqual(expenses[0].description, "Lunch with team")

    def test_pending_items_repository(self):
        payload = {"food_name": "Oatmeal", "calories": 300.0}
        item_id = self.pending_repo.create(
            item_type="FOOD",
            structured_payload=payload,
            raw_payload="Oatmeal with almonds",
            user_notes="Breakfast"
        )
        self.assertGreater(item_id, 0)

        item = self.pending_repo.get_by_id(item_id)
        self.assertIsNotNone(item)
        self.assertEqual(item.item_type, "FOOD")
        self.assertEqual(item.status, "PENDING")
        self.assertEqual(item.structured_payload, payload)

        pending_list = self.pending_repo.list_by_status("PENDING")
        self.assertEqual(len(pending_list), 1)

        # Update status
        self.pending_repo.update_status(item_id, "CONFIRMED")
        item_updated = self.pending_repo.get_by_id(item_id)
        self.assertEqual(item_updated.status, "CONFIRMED")
        self.assertIsNotNone(item_updated.resolved_at)


if __name__ == "__main__":
    unittest.main()
