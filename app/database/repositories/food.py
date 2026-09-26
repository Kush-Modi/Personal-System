"""Food records repository."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from app.database.repositories.base import BaseRepository


@dataclass
class FoodRecord:
    id: int
    food_name: str
    calories: float
    created_at: str


class FoodRepository(BaseRepository):
    """Repository handling all food and calorie database interactions."""

    def add(self, food_name: str, calories: float, record_date: Optional[date] = None) -> int:
        """Insert a new food record. Returns inserted record ID."""
        with self.connection() as conn:
            cursor = conn.cursor()
            if record_date:
                cursor.execute(
                    """
                    INSERT INTO food (food_name, calories, created_at)
                    VALUES (?, ?, ? || ' 12:00:00');
                    """,
                    (food_name, calories, record_date.isoformat())
                )
            else:
                cursor.execute(
                    "INSERT INTO food (food_name, calories) VALUES (?, ?);",
                    (food_name, calories)
                )
            return cursor.lastrowid

    def get_by_id(self, food_id: int) -> Optional[FoodRecord]:
        """Fetch a single food record by its primary key ID."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, food_name, calories, created_at FROM food WHERE id = ?;",
                (food_id,)
            )
            row = cursor.fetchone()
            if row:
                return FoodRecord(
                    id=row["id"],
                    food_name=row["food_name"],
                    calories=row["calories"],
                    created_at=row["created_at"]
                )
            return None

    def get_for_date(self, target_date: date) -> List[FoodRecord]:
        """Fetch all food records for a specific date in chronological order."""
        date_str = target_date.isoformat()
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, food_name, calories, created_at
                FROM food
                WHERE DATE(created_at, 'localtime') = ?
                ORDER BY id ASC;
                """,
                (date_str,)
            )
            return [
                FoodRecord(
                    id=row["id"],
                    food_name=row["food_name"],
                    calories=row["calories"],
                    created_at=row["created_at"]
                )
                for row in cursor.fetchall()
            ]

    def update(self, food_id: int, food_name: str, calories: float) -> bool:
        """Update food name and calories for a given food ID."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE food
                SET food_name = ?, calories = ?
                WHERE id = ?;
                """,
                (food_name, calories, food_id)
            )
            return cursor.rowcount > 0

    def delete(self, food_id: int) -> bool:
        """Delete a food record by ID."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM food WHERE id = ?;", (food_id,))
            return cursor.rowcount > 0

    def get_date_stats(self, target_date: date) -> Tuple[int, float]:
        """Return (count, total_calories) for a specific date."""
        date_str = target_date.isoformat()
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(calories), 0.0)
                FROM food
                WHERE DATE(created_at, 'localtime') = ?;
                """,
                (date_str,)
            )
            row = cursor.fetchone()
            return int(row[0]), float(row[1])

    def get_total_calories_range(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Tuple[float, int, float]:
        """Return (total_calories, distinct_days, average_per_day) across date range."""
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
                SELECT COALESCE(SUM(calories), 0.0), COUNT(DISTINCT DATE(created_at, 'localtime'))
                FROM food
                {where_clause};
                """,
                params
            )
            row = cursor.fetchone()
            total_cals = float(row[0]) if row else 0.0
            days = int(row[1]) if row and row[1] else 1
            avg = total_cals / max(1, days)
            return total_cals, days, avg

