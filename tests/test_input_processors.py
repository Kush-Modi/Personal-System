"""Tests for input processors and deterministic mock extraction."""

import unittest
from app.domain.models import InputSource, ItemType
from app.input.mock_processor import MockInputProcessor


class TestInputProcessors(unittest.TestCase):
    """Test deterministic text and media input processing."""

    def setUp(self):
        self.processor = MockInputProcessor()

    def test_mock_food_command(self):
        res = self.processor.process_text("mock food Paneer Tikka 420")
        self.assertTrue(res.success)
        self.assertEqual(res.item_type, ItemType.FOOD.value)
        self.assertEqual(res.payload["food_name"], "Paneer Tikka")
        self.assertEqual(res.payload["calories"], 420.0)
        self.assertEqual(res.source, InputSource.MOCK.value)

    def test_mock_expense_command(self):
        res = self.processor.process_text("mock expense 1250.0 Shopping Amazon India")
        self.assertTrue(res.success)
        self.assertEqual(res.item_type, ItemType.EXPENSE.value)
        self.assertEqual(res.payload["amount"], 1250.0)
        self.assertEqual(res.payload["category"], "Shopping")
        self.assertEqual(res.payload["merchant"], "Amazon India")

    def test_mock_task_command(self):
        res = self.processor.process_text("mock task Submit research paper")
        self.assertTrue(res.success)
        self.assertEqual(res.item_type, ItemType.TASK.value)
        self.assertEqual(res.payload["title"], "Submit research paper")

    def test_natural_language_food_heuristic(self):
        res = self.processor.process_text("had 2 rotis and dal 350 kcal")
        self.assertTrue(res.success)
        self.assertEqual(res.item_type, ItemType.FOOD.value)
        self.assertEqual(res.payload["food_name"], "2 rotis and dal")
        self.assertEqual(res.payload["calories"], 350.0)

    def test_natural_language_expense_heuristic(self):
        res = self.processor.process_text("spent 180 on coffee at starbucks")
        self.assertTrue(res.success)
        self.assertEqual(res.item_type, ItemType.EXPENSE.value)
        self.assertEqual(res.payload["amount"], 180.0)
        self.assertEqual(res.payload["category"], "Coffee")
        self.assertEqual(res.payload["merchant"], "starbucks")

    def test_unrecognized_text(self):
        res = self.processor.process_text("hello there how are you")
        self.assertFalse(res.success)
        self.assertIsNotNone(res.error_message)

    def test_photo_processing_mock(self):
        # Default food
        food_res = self.processor.process_photo("dummy.jpg", caption="Lunch today")
        self.assertTrue(food_res.success)
        self.assertEqual(food_res.item_type, ItemType.FOOD.value)

        # Receipt caption
        receipt_res = self.processor.process_photo("receipt.jpg", caption="Grocery receipt")
        self.assertTrue(receipt_res.success)
        self.assertEqual(receipt_res.item_type, ItemType.EXPENSE.value)
        self.assertEqual(receipt_res.payload["category"], "Groceries")


if __name__ == "__main__":
    unittest.main()
