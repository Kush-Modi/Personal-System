"""Tests for Food Memory repository and domain service."""

import tempfile
import unittest
from pathlib import Path

from app.database.migrations import run_migrations
from app.database.repositories.food_memory import FoodMemoryRepository
from app.services.food_memory.service import FoodMemoryService


class TestFoodMemory(unittest.TestCase):
    """Test suite for learned food memory repository and service."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_memory.db"
        run_migrations(self.db_path)
        self.repo = FoodMemoryRepository(self.db_path)
        self.service = FoodMemoryService(self.repo)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_upsert_and_find_match(self):
        # Initial learning
        rec = self.service.record_confirmed_food(
            food_name="Paneer Butter Masala",
            calories=420.0,
            unit="bowl",
            confidence=1.0,
            source="USER_CONFIRMED"
        )
        self.assertEqual(rec.canonical_name, "paneer butter masala")
        self.assertEqual(rec.default_calories, 420.0)
        self.assertEqual(rec.use_count, 1)

        # Exact match
        found = self.service.find_match("Paneer Butter Masala")
        self.assertIsNotNone(found)
        self.assertEqual(found.default_calories, 420.0)

        # Second record updates count and calories
        rec2 = self.service.record_confirmed_food(
            food_name="paneer butter masala",
            calories=450.0,
            unit="bowl"
        )
        self.assertEqual(rec2.use_count, 2)
        self.assertEqual(rec2.default_calories, 450.0)

    def test_search_and_context_prompt(self):
        self.service.record_confirmed_food("Moong Dal Khichdi", 320.0, unit="plate")
        self.service.record_confirmed_food("Wheat Roti", 80.0, unit="piece")
        self.service.record_confirmed_food("Cold Coffee", 180.0, unit="glass")

        # Partial search
        results = self.service.search("khichdi")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].canonical_name, "moong dal khichdi")

        # Context prompt building
        context_str = self.service.get_memory_context_prompt(query_hint="khichdi")
        self.assertIn("moong dal khichdi", context_str)
        self.assertIn("320 kcal", context_str)
        self.assertIn("wheat roti", context_str)


if __name__ == "__main__":
    unittest.main()
