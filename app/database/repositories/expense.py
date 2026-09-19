"""Expense records repository."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from app.database.repositories.base import BaseRepository


@dataclass
class ExpenseRecord:
    id: int
    amount: float
    category: str
    description: Optional[str]
    created_at: str


class ExpenseRepository(BaseRepository):
    """Repository handling all expense database interactions."""

    def add(self, amount: float, category: str, description: Optional[str] = None) -> int:
        """Insert a new expense record."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO expenses (amount, category, description)
                VALUES (?, ?, ?);
                """,
                (amount, category, description)
            )
            return cursor.lastrowid

    def get_for_date(self, target_date: date) -> List[ExpenseRecord]:
        """Fetch all expenses for a specific date."""
        date_str = target_date.isoformat()
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, amount, category, description, created_at
                FROM expenses
                WHERE DATE(created_at, 'localtime') = ?
                ORDER BY id ASC;
                """,
                (date_str,)
            )
            return [
                ExpenseRecord(
                    id=row["id"],
                    amount=row["amount"],
                    category=row["category"],
                    description=row["description"],
                    created_at=row["created_at"]
                )
                for row in cursor.fetchall()
            ]
