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

    def get_total_spend(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[str] = None
    ) -> float:
        """Fetch total spend across date range with optional category filter."""
        conditions = []
        params = []
        if start_date:
            conditions.append("DATE(created_at, 'localtime') >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("DATE(created_at, 'localtime') <= ?")
            params.append(end_date.isoformat())
        if category:
            conditions.append("LOWER(category) = LOWER(?)")
            params.append(category.strip())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COALESCE(SUM(amount), 0.0) FROM expenses {where_clause};",
                params
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def get_category_totals(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[tuple]:
        """Fetch spend grouped by category (category, total_amount, count)."""
        conditions = []
        params = []
        if start_date:
            conditions.append("DATE(created_at, 'localtime') >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("DATE(created_at, 'localtime') <= ?")
            params.append(end_date.isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT category, COALESCE(SUM(amount), 0.0) as total, COUNT(*) as cnt
                FROM expenses
                {where_clause}
                GROUP BY category
                ORDER BY total DESC;
                """,
                params
            )
            return [(row["category"], float(row["total"]), int(row["cnt"])) for row in cursor.fetchall()]

    def get_highest_expense(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Optional[ExpenseRecord]:
        """Fetch highest expense record in period."""
        conditions = []
        params = []
        if start_date:
            conditions.append("DATE(created_at, 'localtime') >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("DATE(created_at, 'localtime') <= ?")
            params.append(end_date.isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT id, amount, category, description, created_at
                FROM expenses
                {where_clause}
                ORDER BY amount DESC LIMIT 1;
                """,
                params
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ExpenseRecord(
                id=row["id"],
                amount=row["amount"],
                category=row["category"],
                description=row["description"],
                created_at=row["created_at"]
            )

