"""Weight tracking and periodic reports service."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from app.core.exceptions import ValidationError
from app.database.repositories.food import FoodRepository
from app.database.repositories.weight import WeightRepository


@dataclass
class WeeklyReportData:
    start_date: date
    end_date: date
    daily_weights: List[Tuple[date, Optional[float]]]
    weight_stats: Optional[dict]
    daily_calories: List[Tuple[date, int, float]]  # (day, count, calories)
    total_calories: float
    daily_average_calories: float
    total_food_entries: int


@dataclass
class MonthlyReportData:
    start_date: date
    end_date: date
    daily_weights: List[Tuple[date, Optional[float]]]
    weight_stats: Optional[dict]
    daily_calories: List[Tuple[date, int, float]]
    total_calories: float
    average_per_logged_day: float
    total_food_entries: int


class WeightService:
    """Service encapsulating weight records and analytical reports."""

    def __init__(
        self,
        weight_repository: Optional[WeightRepository] = None,
        food_repository: Optional[FoodRepository] = None
    ):
        self.weight_repo = weight_repository or WeightRepository()
        self.food_repo = food_repository or FoodRepository()

    def record_weight(self, target_date: date, weight: float) -> Tuple[bool, float]:
        """Record or update weight for a given date. Returns (is_updated, weight)."""
        if weight <= 0 or weight > 500:
            raise ValidationError("Weight must be between 0 and 500 kg.")

        is_updated, _ = self.weight_repo.upsert_for_date(target_date, weight)
        return is_updated, weight

    def get_weight_for_date(self, target_date: date) -> Optional[float]:
        """Fetch recorded weight for a specific date."""
        return self.weight_repo.get_for_date(target_date)

    def get_recent_history(self, limit: int = 30) -> List[Tuple[float, str]]:
        """Fetch recent weight history."""
        return self.weight_repo.get_recent(limit)

    def delete_weight_for_date(self, target_date: date) -> bool:
        """Delete weight for a specific date."""
        return self.weight_repo.delete_for_date(target_date)

    def get_weekly_report(self, reference_date: date) -> WeeklyReportData:
        """Generate full weekly metrics from Monday to Sunday around reference date."""
        start_date = reference_date - timedelta(days=reference_date.weekday())
        end_date = start_date + timedelta(days=6)

        daily_weights: List[Tuple[date, Optional[float]]] = []
        daily_calories: List[Tuple[date, int, float]] = []
        valid_weights: List[Tuple[date, float]] = []

        total_food = 0
        total_calories = 0.0

        for i in range(7):
            day = start_date + timedelta(days=i)
            
            # Weight for day
            w = self.weight_repo.get_for_date(day)
            daily_weights.append((day, w))
            if w is not None:
                valid_weights.append((day, w))

            # Food for day
            count, cals = self.food_repo.get_date_stats(day)
            daily_calories.append((day, count, cals))
            total_food += count
            total_calories += cals

        # Weight stats
        weight_stats = None
        if valid_weights:
            start_w = valid_weights[0][1]
            latest_w = valid_weights[-1][1]
            values = [val for _, val in valid_weights]
            weight_stats = {
                "start": start_w,
                "latest": latest_w,
                "change": latest_w - start_w,
                "average": sum(values) / len(values),
                "lowest": min(values),
                "highest": max(values),
            }

        daily_avg_cals = total_calories / 7.0

        return WeeklyReportData(
            start_date=start_date,
            end_date=end_date,
            daily_weights=daily_weights,
            weight_stats=weight_stats,
            daily_calories=daily_calories,
            total_calories=total_calories,
            daily_average_calories=daily_avg_cals,
            total_food_entries=total_food,
        )

    def get_monthly_report(self, reference_date: date) -> MonthlyReportData:
        """Generate full monthly metrics for the calendar month of reference date."""
        year = reference_date.year
        month = reference_date.month

        if month == 12:
            next_month = datetime(year + 1, 1, 1).date()
        else:
            next_month = datetime(year, month + 1, 1).date()

        start_date = datetime(year, month, 1).date()
        end_date = next_month - timedelta(days=1)

        daily_weights: List[Tuple[date, Optional[float]]] = []
        daily_calories: List[Tuple[date, int, float]] = []
        valid_weights: List[Tuple[date, float]] = []

        total_food = 0
        total_calories = 0.0
        days_with_food = 0

        curr_day = start_date
        while curr_day <= end_date:
            w = self.weight_repo.get_for_date(curr_day)
            daily_weights.append((curr_day, w))
            if w is not None:
                valid_weights.append((curr_day, w))

            count, cals = self.food_repo.get_date_stats(curr_day)
            daily_calories.append((curr_day, count, cals))
            total_food += count
            total_calories += cals
            if cals > 0:
                days_with_food += 1

            curr_day += timedelta(days=1)

        weight_stats = None
        if valid_weights:
            start_w = valid_weights[0][1]
            latest_w = valid_weights[-1][1]
            values = [val for _, val in valid_weights]
            weight_stats = {
                "start": start_w,
                "latest": latest_w,
                "change": latest_w - start_w,
                "average": sum(values) / len(values),
                "lowest": min(values),
                "highest": max(values),
            }

        avg_logged = (total_calories / days_with_food) if days_with_food > 0 else 0.0

        return MonthlyReportData(
            start_date=start_date,
            end_date=end_date,
            daily_weights=daily_weights,
            weight_stats=weight_stats,
            daily_calories=daily_calories,
            total_calories=total_calories,
            average_per_logged_day=avg_logged,
            total_food_entries=total_food,
        )
