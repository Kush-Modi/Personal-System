"""Weight records repository."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from app.database.repositories.base import BaseRepository


@dataclass
class WeightRecord:
    id: int
    weight: float
    created_at: str


class WeightRepository(BaseRepository):
    """Repository handling all weight database interactions."""

    def upsert_for_date(self, target_date: date, weight: float) -> Tuple[bool, int]:
        """
        Record or update weight for a specific date.
        Returns (is_updated, record_id).
        """
        date_str = target_date.isoformat()
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id
                FROM weights
                WHERE DATE(created_at, 'localtime') = ?;
                """,
                (date_str,)
            )
            existing = cursor.fetchone()

            if existing:
                record_id = existing["id"]
                cursor.execute(
                    """
                    UPDATE weights
                    SET weight = ?
                    WHERE id = ?;
                    """,
                    (weight, record_id)
                )
                return True, record_id
            else:
                cursor.execute(
                    """
                    INSERT INTO weights (weight, created_at)
                    VALUES (?, ? || ' 12:00:00');
                    """,
                    (weight, date_str)
                )
                return False, cursor.lastrowid

    def get_for_date(self, target_date: date) -> Optional[float]:
        """Fetch weight value recorded for a specific date."""
        date_str = target_date.isoformat()
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT weight
                FROM weights
                WHERE DATE(created_at, 'localtime') = ?;
                """,
                (date_str,)
            )
            row = cursor.fetchone()
            return float(row["weight"]) if row else None

    def get_recent(self, limit: int = 30) -> List[Tuple[float, str]]:
        """Fetch most recent weight entries up to limit."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT weight, created_at
                FROM weights
                ORDER BY DATE(created_at, 'localtime') DESC
                LIMIT ?;
                """,
                (limit,)
            )
            return [(float(row["weight"]), str(row["created_at"])) for row in cursor.fetchall()]

    def delete_for_date(self, target_date: date) -> bool:
        """Delete weight entry for a specific date."""
        date_str = target_date.isoformat()
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM weights
                WHERE DATE(created_at, 'localtime') = ?;
                """,
                (date_str,)
            )
            return cursor.rowcount > 0

    def get_range(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Tuple[float, str]]:
        """Fetch weight entries in chronological order across date range."""
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
                SELECT weight, created_at
                FROM weights
                {where_clause}
                ORDER BY DATE(created_at, 'localtime') ASC;
                """,
                params
            )
            return [(float(row["weight"]), str(row["created_at"])) for row in cursor.fetchall()]

