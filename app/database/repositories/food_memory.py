"""Repository for persisting and querying learned food memory."""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.database.repositories.base import BaseRepository


@dataclass
class FoodMemoryRecord:
    id: int
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    default_calories: float = 0.0
    default_unit: str = "serving"
    default_portion_grams: Optional[float] = None
    confidence: float = 1.0
    source: str = "USER_CONFIRMED"
    use_count: int = 1
    last_used_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FoodMemoryRepository(BaseRepository):
    """Database operations for learned food items and caloric estimates."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        super().__init__(db_path)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> FoodMemoryRecord:
        aliases_raw = row["aliases_json"]
        aliases = []
        if aliases_raw:
            try:
                aliases = json.loads(aliases_raw)
            except Exception:
                aliases = []

        return FoodMemoryRecord(
            id=row["id"],
            canonical_name=row["canonical_name"],
            aliases=aliases,
            default_calories=float(row["default_calories"]),
            default_unit=row["default_unit"] or "serving",
            default_portion_grams=float(row["default_portion_grams"]) if row["default_portion_grams"] is not None else None,
            confidence=float(row["confidence"]) if row["confidence"] is not None else 1.0,
            source=row["source"] or "USER_CONFIRMED",
            use_count=int(row["use_count"]) if row["use_count"] is not None else 1,
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def upsert(
        self,
        canonical_name: str,
        default_calories: float,
        aliases: Optional[List[str]] = None,
        default_unit: str = "serving",
        default_portion_grams: Optional[float] = None,
        confidence: float = 1.0,
        source: str = "USER_CONFIRMED",
    ) -> FoodMemoryRecord:
        """Insert or update a food memory item with normalized canonical name."""
        name_clean = canonical_name.strip().lower()
        aliases_list = [a.strip().lower() for a in (aliases or []) if a and a.strip()]
        aliases_json = json.dumps(aliases_list)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.connection() as conn:
            cursor = conn.cursor()
            # Check if exists
            cursor.execute(
                "SELECT id, use_count, aliases_json FROM food_memory WHERE LOWER(canonical_name) = ?;",
                (name_clean,)
            )
            existing = cursor.fetchone()

            if existing:
                existing_id = existing["id"]
                existing_count = existing["use_count"] or 0
                # Merge aliases if any
                existing_aliases = []
                if existing["aliases_json"]:
                    try:
                        existing_aliases = json.loads(existing["aliases_json"])
                    except Exception:
                        existing_aliases = []
                merged_aliases = list(set(existing_aliases + aliases_list))

                cursor.execute("""
                    UPDATE food_memory
                    SET default_calories = ?,
                        aliases_json = ?,
                        default_unit = ?,
                        default_portion_grams = COALESCE(?, default_portion_grams),
                        confidence = ?,
                        source = ?,
                        use_count = ?,
                        last_used_at = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (
                    default_calories,
                    json.dumps(merged_aliases),
                    default_unit,
                    default_portion_grams,
                    confidence,
                    source,
                    existing_count + 1,
                    now_str,
                    now_str,
                    existing_id,
                ))
                record_id = existing_id
            else:
                cursor.execute("""
                    INSERT INTO food_memory (
                        canonical_name, aliases_json, default_calories, default_unit,
                        default_portion_grams, confidence, source, use_count, last_used_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?);
                """, (
                    name_clean,
                    aliases_json,
                    default_calories,
                    default_unit,
                    default_portion_grams,
                    confidence,
                    source,
                    now_str,
                    now_str,
                    now_str,
                ))
                record_id = cursor.lastrowid

        return self.get_by_id(record_id)

    def get_by_id(self, item_id: int) -> Optional[FoodMemoryRecord]:
        """Fetch memory item by ID."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM food_memory WHERE id = ?;", (item_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def find_by_name_or_alias(self, query: str) -> Optional[FoodMemoryRecord]:
        """Exact match on canonical name or aliases (case-insensitive)."""
        clean_query = query.strip().lower()
        if not clean_query:
            return None

        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            # 1. Exact match on canonical_name
            cursor.execute(
                "SELECT * FROM food_memory WHERE LOWER(canonical_name) = ? LIMIT 1;",
                (clean_query,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)

            # 2. Check aliases
            cursor.execute("SELECT * FROM food_memory;")
            for row in cursor.fetchall():
                record = self._row_to_record(row)
                if clean_query in [a.lower() for a in record.aliases]:
                    return record

        return None

    def search(self, query: str, limit: int = 10) -> List[FoodMemoryRecord]:
        """Fuzzy/substring search across canonical name and aliases."""
        clean_query = query.strip().lower()
        if not clean_query:
            return []

        results: List[FoodMemoryRecord] = []
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM food_memory WHERE LOWER(canonical_name) LIKE ? ORDER BY use_count DESC LIMIT ?;",
                (f"%{clean_query}%", limit)
            )
            for row in cursor.fetchall():
                results.append(self._row_to_record(row))

        return results

    def get_top_frequent(self, limit: int = 20) -> List[FoodMemoryRecord]:
        """Retrieve most frequently logged food items."""
        results: List[FoodMemoryRecord] = []
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM food_memory ORDER BY use_count DESC, last_used_at DESC LIMIT ?;",
                (limit,)
            )
            for row in cursor.fetchall():
                results.append(self._row_to_record(row))
        return results

    def delete(self, item_id: int) -> bool:
        """Delete a food memory record."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM food_memory WHERE id = ?;", (item_id,))
            return cursor.rowcount > 0
