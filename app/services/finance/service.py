"""Finance and expense business logic service."""

from datetime import date
from typing import List, Optional

from app.core.exceptions import ValidationError
from app.database.repositories.expense import ExpenseRecord, ExpenseRepository


class FinanceService:
    """Service encapsulating expense tracking and financial records."""

    def __init__(self, repository: Optional[ExpenseRepository] = None):
        self.repository = repository or ExpenseRepository()

    def add_expense(
        self,
        amount: float,
        category: str,
        description: Optional[str] = None
    ) -> int:
        """Add an expense record with basic validation."""
        if amount <= 0:
            raise ValidationError("Expense amount must be positive.")
        cleaned_cat = category.strip()
        if not cleaned_cat:
            raise ValidationError("Expense category cannot be empty.")

        return self.repository.add(amount, cleaned_cat, description)

    def get_expenses_for_date(self, target_date: date) -> List[ExpenseRecord]:
        """Fetch all expenses recorded for a specific date."""
        return self.repository.get_for_date(target_date)
