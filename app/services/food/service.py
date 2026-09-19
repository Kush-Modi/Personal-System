"""Food and nutrition business logic service."""

from datetime import date
from typing import List, Optional, Tuple

from app.core.exceptions import NotFoundError, ValidationError
from app.database.repositories.food import FoodRecord, FoodRepository


class FoodService:
    """Service encapsulating all food-related business rules."""

    def __init__(self, repository: Optional[FoodRepository] = None):
        self.repository = repository or FoodRepository()

    def add_food(self, name: str, calories: float) -> FoodRecord:
        """Add a new food item with validation."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("Food name cannot be empty.")

        if calories <= 0 or calories > 10000:
            raise ValidationError("Calories must be between 1 and 10,000 kcal.")

        record_id = self.repository.add(cleaned_name, calories)
        record = self.repository.get_by_id(record_id)
        if not record:
            return FoodRecord(id=record_id, food_name=cleaned_name, calories=calories, created_at="")
        return record

    def get_food_for_date(self, target_date: date) -> Tuple[List[FoodRecord], float]:
        """Fetch all food items for a date along with total calories."""
        records = self.repository.get_for_date(target_date)
        total_calories = sum(r.calories for r in records)
        return records, total_calories

    def edit_food_by_index(
        self,
        target_date: date,
        index_1_based: int,
        name: str,
        calories: float
    ) -> FoodRecord:
        """Edit a food record identified by its 1-based daily display index."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("Food name cannot be empty.")

        if calories <= 0 or calories > 10000:
            raise ValidationError("Calories must be between 1 and 10,000 kcal.")

        records = self.repository.get_for_date(target_date)
        if index_1_based < 1 or index_1_based > len(records):
            raise NotFoundError("Food entry not found.")

        target_record = records[index_1_based - 1]
        self.repository.update(target_record.id, cleaned_name, calories)
        return FoodRecord(
            id=target_record.id,
            food_name=cleaned_name,
            calories=calories,
            created_at=target_record.created_at
        )

    def delete_food_by_index(self, target_date: date, index_1_based: int) -> bool:
        """Delete a food record identified by its 1-based daily display index."""
        records = self.repository.get_for_date(target_date)
        if index_1_based < 1 or index_1_based > len(records):
            raise NotFoundError("Food entry not found.")

        target_record = records[index_1_based - 1]
        return self.repository.delete(target_record.id)

    def get_date_stats(self, target_date: date) -> Tuple[int, float]:
        """Get (count, total_calories) for a date."""
        return self.repository.get_date_stats(target_date)
