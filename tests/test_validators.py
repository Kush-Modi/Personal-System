"""Tests for two-level validation (Schema and Domain)."""

import unittest
from app.core.exceptions import DomainValidationError, SchemaValidationError
from app.domain.models import ItemType
from app.domain.validators import (
    validate_expense_domain,
    validate_expense_schema,
    validate_food_domain,
    validate_food_schema,
    validate_payload,
    validate_task_domain,
    validate_task_schema,
)


class TestValidators(unittest.TestCase):
    """Test Level 1 (Schema) and Level 2 (Domain) validators."""

    def test_food_schema_valid(self):
        payload = {"food_name": "Paneer Tikka", "calories": "420", "date": "2026-09-19"}
        obj = validate_food_schema(payload)
        self.assertEqual(obj.food_name, "Paneer Tikka")
        self.assertEqual(obj.calories, 420.0)
        self.assertEqual(obj.date, "2026-09-19")

    def test_food_schema_missing_calories(self):
        with self.assertRaises(SchemaValidationError):
            validate_food_schema({"food_name": "Apple"})

    def test_food_schema_invalid_calories_type(self):
        with self.assertRaises(SchemaValidationError):
            validate_food_schema({"food_name": "Apple", "calories": "invalid_num"})

    def test_food_schema_invalid_date_format(self):
        with self.assertRaises(SchemaValidationError):
            validate_food_schema({"food_name": "Apple", "calories": 100, "date": "19-09-2026"})

    def test_food_domain_validations(self):
        obj = validate_food_schema({"food_name": "Salad", "calories": 150})
        validate_food_domain(obj)  # Should pass

        # Empty name
        obj_empty = validate_food_schema({"food_name": "   ", "calories": 150})
        with self.assertRaises(DomainValidationError):
            validate_food_domain(obj_empty)

        # Zero or negative calories
        obj_zero = validate_food_schema({"food_name": "Salad", "calories": 0})
        with self.assertRaises(DomainValidationError):
            validate_food_domain(obj_zero)

        # Unreasonable upper bound
        obj_huge = validate_food_schema({"food_name": "Feast", "calories": 15000})
        with self.assertRaises(DomainValidationError):
            validate_food_domain(obj_huge)

    def test_expense_schema_and_domain(self):
        payload = {"amount": "250.50", "category": "Groceries", "merchant": "Supermarket"}
        obj = validate_expense_schema(payload)
        self.assertEqual(obj.amount, 250.50)
        self.assertEqual(obj.category, "Groceries")
        self.assertEqual(obj.merchant, "Supermarket")
        validate_expense_domain(obj)

        # Invalid amount
        with self.assertRaises(SchemaValidationError):
            validate_expense_schema({"category": "Groceries"})

        # Negative amount domain error
        obj_neg = validate_expense_schema({"amount": -50, "category": "Food"})
        with self.assertRaises(DomainValidationError):
            validate_expense_domain(obj_neg)

    def test_task_schema_and_domain(self):
        payload = {"title": "Submit project", "due_date": "2026-09-30"}
        obj = validate_task_schema(payload)
        self.assertEqual(obj.title, "Submit project")
        self.assertEqual(obj.due_date, "2026-09-30")
        validate_task_domain(obj)

        with self.assertRaises(DomainValidationError):
            validate_task_domain(validate_task_schema({"title": "  "}))

    def test_comprehensive_validate_payload(self):
        food = validate_payload("FOOD", {"food_name": "Biryani", "calories": 650})
        self.assertEqual(food.food_name, "Biryani")

        exp = validate_payload(ItemType.EXPENSE, {"amount": 100, "category": "Travel"})
        self.assertEqual(exp.amount, 100.0)


if __name__ == "__main__":
    unittest.main()
