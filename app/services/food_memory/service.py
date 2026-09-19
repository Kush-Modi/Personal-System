"""Food Memory Service for managing learned nutritional benchmarks."""

from typing import List, Optional

from app.core.logging import get_logger
from app.database.repositories.food_memory import (
    FoodMemoryRecord,
    FoodMemoryRepository,
)

logger = get_logger("services.food_memory")


class FoodMemoryService:
    """Service for managing the user's localized food dictionary and memory benchmarks."""

    def __init__(self, repository: Optional[FoodMemoryRepository] = None):
        self.repo = repository or FoodMemoryRepository()

    def record_confirmed_food(
        self,
        food_name: str,
        calories: float,
        unit: str = "serving",
        confidence: float = 1.0,
        source: str = "USER_CONFIRMED"
    ) -> FoodMemoryRecord:
        """Learn or update a confirmed food item in memory."""
        record = self.repo.upsert(
            canonical_name=food_name,
            default_calories=calories,
            default_unit=unit,
            confidence=confidence,
            source=source
        )
        logger.info(f"Learned food memory for '{record.canonical_name}': {record.default_calories:.0f} kcal (uses: {record.use_count})")
        return record

    def find_match(self, query: str) -> Optional[FoodMemoryRecord]:
        """Look up exact match in food memory."""
        return self.repo.find_by_name_or_alias(query)

    def search(self, query: str, limit: int = 10) -> List[FoodMemoryRecord]:
        """Search memory for partial matches."""
        return self.repo.search(query, limit=limit)

    def get_memory_context_prompt(self, query_hint: Optional[str] = None, max_items: int = 20) -> str:
        """
        Build concise memory context text block to guide LLM estimations.
        Prioritizes matches relevant to query_hint, followed by most frequent items.
        """
        items: List[FoodMemoryRecord] = []
        seen_ids = set()

        # If query hint exists, find direct matches first
        if query_hint:
            matched = self.repo.search(query_hint, limit=5)
            for m in matched:
                if m.id not in seen_ids:
                    items.append(m)
                    seen_ids.add(m.id)

        # Fill with top frequent items
        frequent = self.repo.get_top_frequent(limit=max_items)
        for f in frequent:
            if f.id not in seen_ids and len(items) < max_items:
                items.append(f)
                seen_ids.add(f.id)

        if not items:
            return ""

        lines = ["User's Known Food Benchmarks (use these caloric values when matching):"]
        for item in items:
            lines.append(f"- {item.canonical_name}: {item.default_calories:.0f} kcal per {item.default_unit} (confidence: {item.confidence:.2f})")

        return "\n".join(lines)
