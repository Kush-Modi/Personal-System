"""Safe, deterministic Query Planner and Analytics Service.

STRICT INVARIANTS:
1. NO AI-generated SQL is ever executed.
2. AI returns structured query intent (domain, operation, date_range, filters).
3. QueryPlanner maps structured query intent to explicit repository aggregation methods.
4. Calculations are executed strictly in SQLite/Python with authoritative results.
5. Natural language response formatter uses factual numbers with zero numeric hallucination.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.database.repositories.expense import ExpenseRecord, ExpenseRepository
from app.database.repositories.food import FoodRepository
from app.database.repositories.reminder import ReminderRepository
from app.database.repositories.task import TaskRepository
from app.database.repositories.weight import WeightRepository

logger = get_logger("services.analytics")


def parse_date_range(date_range_dict: Optional[Dict[str, Any]]) -> Tuple[Optional[date], Optional[date], str]:
    """
    Parse date range specifications like 'today', 'yesterday', 'this_week', 'this_month', 'last_week', 'last_month'
    or explicit 'YYYY-MM-DD' start/end strings.
    Returns: (start_date, end_date, human_label)
    """
    today = date.today()
    if not date_range_dict or not isinstance(date_range_dict, dict):
        return today, today, "today"

    range_key = str(date_range_dict.get("range") or date_range_dict.get("period") or "").lower().strip()
    start_str = date_range_dict.get("start")
    end_str = date_range_dict.get("end")

    if start_str and end_str:
        try:
            s = date.fromisoformat(str(start_str))
            e = date.fromisoformat(str(end_str))
            return s, e, f"{s.isoformat()} to {e.isoformat()}"
        except Exception:
            pass

    if range_key in ("today", "current_day"):
        return today, today, "today"
    elif range_key in ("yesterday", "prev_day"):
        y = today - timedelta(days=1)
        return y, y, "yesterday"
    elif range_key in ("this_week", "current_week", "week"):
        start = today - timedelta(days=today.weekday())
        return start, today, "this week"
    elif range_key in ("last_week", "previous_week"):
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end, "last week"
    elif range_key in ("this_month", "current_month", "month"):
        start = today.replace(day=1)
        return start, today, "this month"
    elif range_key in ("last_month", "previous_month"):
        first_this_month = today.replace(day=1)
        last_day_prev = first_this_month - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        return start, last_day_prev, "last month"
    elif range_key in ("all_time", "total"):
        return None, None, "all time"

    # Default to today
    return today, today, "today"


class AnalyticsQueryService:
    """Safe analytical query planner executing explicit repository operations."""

    def __init__(
        self,
        food_repo: Optional[FoodRepository] = None,
        expense_repo: Optional[ExpenseRepository] = None,
        weight_repo: Optional[WeightRepository] = None,
        task_repo: Optional[TaskRepository] = None,
        reminder_repo: Optional[ReminderRepository] = None,
    ):
        self.food_repo = food_repo or FoodRepository()
        self.expense_repo = expense_repo or ExpenseRepository()
        self.weight_repo = weight_repo or WeightRepository()
        self.task_repo = task_repo or TaskRepository()
        self.reminder_repo = reminder_repo or ReminderRepository()

    def execute_query(self, query_plan: Dict[str, Any]) -> str:
        """
        Execute query plan deterministically and return natural summary.
        query_plan schema:
        {
          "domain": "FOOD|EXPENSE|WEIGHT|TASK|REMINDER|MULTI",
          "operation": "TOTAL|AVERAGE|LIST|HIGHEST|LOWEST|TREND|COUNT|SUMMARY",
          "date_range": {...},
          "filters": {...}
        }
        """
        domain = str(query_plan.get("domain", "OTHER")).upper().strip()
        op = str(query_plan.get("operation", "TOTAL")).upper().strip()
        date_range = query_plan.get("date_range", {})
        filters = query_plan.get("filters") or {}

        start_d, end_d, range_label = parse_date_range(date_range)

        try:
            if domain == "FOOD":
                return self._query_food(op, start_d, end_d, range_label, filters)
            elif domain == "EXPENSE":
                return self._query_expense(op, start_d, end_d, range_label, filters)
            elif domain == "WEIGHT":
                return self._query_weight(op, start_d, end_d, range_label, filters)
            elif domain == "TASK":
                return self._query_task(op, filters)
            elif domain == "REMINDER":
                return self._query_reminder(op, filters)
            else:
                return "I couldn't match this query to a specific log. You can ask about your food calories, expenses, weight, tasks, or reminders!"
        except Exception as e:
            logger.error(f"Error executing data query: {e}", exc_info=True)
            return "⚠️ An error occurred while retrieving your data."

    def _query_food(self, op: str, start_d: Optional[date], end_d: Optional[date], label: str, filters: dict) -> str:
        if start_d and end_d and start_d == end_d:
            # Single day stats
            count, total = self.food_repo.get_date_stats(start_d)
            records = self.food_repo.get_for_date(start_d)
            if not records:
                return f"🍽 No food logged for {label}."
            items_str = ", ".join(f"{r.food_name} ({r.calories:.0f} kcal)" for r in records)
            return f"🍽 *Food for {label}:*\n\n• Total: *{total:.0f} kcal* across {count} item(s).\n• Log: {items_str}"

        total_cals, days, avg = self.food_repo.get_total_calories_range(start_d, end_d)
        if total_cals == 0:
            return f"🍽 No food entries found for {label}."

        if op in ("AVERAGE", "AVG"):
            return f"🍽 *Average Daily Calories ({label}):*\n\n*{avg:.0f} kcal/day* across {days} logged day(s) (Total: {total_cals:.0f} kcal)."
        else:
            return f"🍽 *Total Calories ({label}):*\n\n*{total_cals:.0f} kcal* (Daily average: ~{avg:.0f} kcal across {days} logged day(s))."

    def _query_expense(self, op: str, start_d: Optional[date], end_d: Optional[date], label: str, filters: dict) -> str:
        cat = filters.get("category")
        if cat:
            total = self.expense_repo.get_total_spend(start_d, end_d, category=cat)
            return f"💳 *Spend on {cat.title()} ({label}):*\n\n*₹{total:.2f}*"

        if op in ("HIGHEST", "MAX"):
            highest = self.expense_repo.get_highest_expense(start_d, end_d)
            if not highest:
                return f"💳 No expense entries found for {label}."
            desc = f" ({highest.description})" if highest.description else ""
            return f"💳 *Highest Expense ({label}):*\n\n*₹{highest.amount:.2f}* on *{highest.category}*{desc}"

        total = self.expense_repo.get_total_spend(start_d, end_d)
        cat_totals = self.expense_repo.get_category_totals(start_d, end_d)
        if total == 0:
            return f"💳 No expenses recorded for {label}."

        breakdown = "\n".join(f"• {c}: ₹{t:.2f} ({cnt}x)" for c, t, cnt in cat_totals[:5])
        return f"💳 *Total Spend ({label}):*\n\n*₹{total:.2f}*\n\n*Top Categories:*\n{breakdown}"

    def _query_weight(self, op: str, start_d: Optional[date], end_d: Optional[date], label: str, filters: dict) -> str:
        if start_d and end_d and start_d == end_d:
            w = self.weight_repo.get_for_date(start_d)
            if w is None:
                return f"⚖️ No weight recorded for {label}."
            return f"⚖️ *Weight for {label}:* *{w:.1f} kg*"

        entries = self.weight_repo.get_range(start_d, end_d)
        if not entries:
            recent = self.weight_repo.get_recent(limit=1)
            if recent:
                w, d = recent[0]
                return f"⚖️ No weight found for {label}. Latest recorded weight is *{w:.1f} kg* ({d[:10]})."
            return f"⚖️ No weight records found for {label}."

        weights = [e[0] for e in entries]
        latest_w = weights[-1]
        first_w = weights[0]
        change = latest_w - first_w
        min_w = min(weights)
        max_w = max(weights)

        change_sign = "+" if change > 0 else ""
        return (
            f"⚖️ *Weight Trend ({label}):*\n\n"
            f"• Latest: *{latest_w:.1f} kg*\n"
            f"• Lowest: *{min_w:.1f} kg*\n"
            f"• Highest: *{max_w:.1f} kg*\n"
            f"• Net Change: *{change_sign}{change:.1f} kg* over {len(weights)} check-in(s)"
        )

    def _query_task(self, op: str, filters: dict) -> str:
        pending = self.task_repo.list_by_status("PENDING", limit=10)
        if not pending:
            return "📋 *You have no pending tasks!* All caught up."
        tasks_str = "\n".join(f"• #{t.id} {t.title}" + (f" (Due: {t.due_at})" if t.due_at else "") for t in pending)
        return f"📋 *Pending Tasks ({len(pending)}):*\n\n{tasks_str}"

    def _query_reminder(self, op: str, filters: dict) -> str:
        upcoming = self.reminder_repo.list_upcoming(limit=10)
        if not upcoming:
            return "🔔 *No upcoming reminders scheduled.*"
        rems_str = "\n".join(f"• #{r.id} {r.reminder_text} at *{r.next_trigger_at or r.remind_at}*" for r in upcoming)
        return f"🔔 *Upcoming Reminders ({len(upcoming)}):*\n\n{rems_str}"
