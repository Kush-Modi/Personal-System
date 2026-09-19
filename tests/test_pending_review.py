"""Tests for end-of-day pending items review service."""

import tempfile
import unittest
from pathlib import Path

from app.database.migrations import run_migrations
from app.database.repositories.pending_items import PendingItemRepository
from app.domain.models import ItemType
from app.services.review.service import PendingReviewService


class TestPendingReviewService(unittest.TestCase):
    """Test end-of-day review logic and 0-item silence rule."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_review.db"
        run_migrations(self.db_path)

        self.repo = PendingItemRepository(self.db_path)
        self.review_service = PendingReviewService(self.repo)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_zero_pending_items_sends_nothing(self):
        count, msg, items = self.review_service.check_pending_review()
        self.assertEqual(count, 0)
        self.assertIsNone(msg)
        self.assertEqual(len(items), 0)

    def test_single_pending_item_triggers_review(self):
        self.repo.create(
            item_type=ItemType.FOOD.value,
            structured_payload={"food_name": "Paneer Burrito", "calories": 550}
        )
        count, msg, items = self.review_service.check_pending_review()
        self.assertEqual(count, 1)
        self.assertIsNotNone(msg)
        self.assertIn("Paneer Burrito", msg)
        self.assertIn("550 kcal", msg)

    def test_multiple_pending_items_summary(self):
        self.repo.create(
            item_type=ItemType.FOOD.value,
            structured_payload={"food_name": "Salad", "calories": 200}
        )
        self.repo.create(
            item_type=ItemType.EXPENSE.value,
            structured_payload={"amount": 450, "category": "Books"}
        )
        count, msg, items = self.review_service.check_pending_review()
        self.assertEqual(count, 2)
        self.assertIsNotNone(msg)
        self.assertIn("2", msg)
        self.assertIn("Salad", msg)
        self.assertIn("Books", msg)


if __name__ == "__main__":
    unittest.main()
