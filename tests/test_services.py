"""Tests for business logic services."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.core.exceptions import NotFoundError, ValidationError
from app.database.migrations import run_migrations
from app.database.repositories.food import FoodRepository
from app.database.repositories.weight import WeightRepository
from app.services.finance.service import FinanceService
from app.services.food.service import FoodService
from app.services.system.service import SystemService
from app.services.weight.service import WeightService


class TestServices(unittest.TestCase):
    """Test business rules, validation, and analytical calculations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_service.db"
        run_migrations(self.db_path)

        self.food_repo = FoodRepository(self.db_path)
        self.weight_repo = WeightRepository(self.db_path)

        self.food_service = FoodService(self.food_repo)
        self.weight_service = WeightService(self.weight_repo, self.food_repo)
        self.finance_service = FinanceService()
        self.system_service = SystemService()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_food_service_validations(self):
        # Empty name
        with self.assertRaises(ValidationError):
            self.food_service.add_food("   ", 500)

        # Invalid calories
        with self.assertRaises(ValidationError):
            self.food_service.add_food("Salad", -10)
        with self.assertRaises(ValidationError):
            self.food_service.add_food("Salad", 12000)

        # Valid add
        rec = self.food_service.add_food("Sandwich", 400.0)
        self.assertEqual(rec.food_name, "Sandwich")
        self.assertEqual(rec.calories, 400.0)

    def test_food_service_1_based_indexing(self):
        today = date.today()
        self.food_service.add_food("Item 1", 100)
        self.food_service.add_food("Item 2", 200)

        # Edit item 2
        edited = self.food_service.edit_food_by_index(today, 2, "Item 2 Updated", 250)
        self.assertEqual(edited.food_name, "Item 2 Updated")
        self.assertEqual(edited.calories, 250)

        # Edit invalid index
        with self.assertRaises(NotFoundError):
            self.food_service.edit_food_by_index(today, 5, "Item 5", 300)

        # Delete item 1
        deleted = self.food_service.delete_food_by_index(today, 1)
        self.assertTrue(deleted)

        # Now only 1 item left
        records, total = self.food_service.get_food_for_date(today)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].food_name, "Item 2 Updated")
        self.assertEqual(total, 250)

    def test_weight_service_validation_and_reports(self):
        today = date.today()
        # Validation
        with self.assertRaises(ValidationError):
            self.weight_service.record_weight(today, -5)
        with self.assertRaises(ValidationError):
            self.weight_service.record_weight(today, 600)

        # Record weights across days
        start_of_week = today - timedelta(days=today.weekday())
        self.weight_service.record_weight(start_of_week, 75.0)
        self.weight_service.record_weight(start_of_week + timedelta(days=1), 74.5)
        self.weight_service.record_weight(start_of_week + timedelta(days=2), 74.0)

        # Add food for one day
        self.food_service.add_food("Dinner", 800)

        # Test weekly report
        report = self.weight_service.get_weekly_report(today)
        self.assertEqual(report.start_date, start_of_week)
        self.assertEqual(report.end_date, start_of_week + timedelta(days=6))
        self.assertIsNotNone(report.weight_stats)
        self.assertAlmostEqual(report.weight_stats["start"], 75.0)
        self.assertAlmostEqual(report.weight_stats["latest"], 74.0)
        self.assertAlmostEqual(report.weight_stats["change"], -1.0)
        self.assertAlmostEqual(report.weight_stats["lowest"], 74.0)
        self.assertAlmostEqual(report.weight_stats["highest"], 75.0)

        # Test monthly report
        month_report = self.weight_service.get_monthly_report(today)
        self.assertIsNotNone(month_report.weight_stats)
        self.assertGreaterEqual(month_report.total_calories, 800)

    def test_system_service_health(self):
        report = self.system_service.get_health_status()
        self.assertIn(report.overall_status, ["HEALTHY", "DEGRADED", "UNHEALTHY"])
        formatted = self.system_service.get_formatted_status_message()
        self.assertIn("System Status", formatted)


if __name__ == "__main__":
    unittest.main()
