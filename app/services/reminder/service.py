"""Reminder domain service and scheduler helper calculations for Asia/Kolkata timezone."""

from datetime import datetime, timedelta
from typing import List, Optional
import zoneinfo

from app.core.exceptions import DomainValidationError, NotFoundError
from app.core.logging import get_logger
from app.database.repositories.reminder import ReminderRecord, ReminderRepository

logger = get_logger("services.reminder")

DEFAULT_TIMEZONE = "Asia/Kolkata"


def calculate_next_recurrence(
    current_remind_at: str,
    recurrence: Optional[str],
    tz_str: str = DEFAULT_TIMEZONE
) -> Optional[str]:
    """Calculate next trigger ISO timestamp for recurring reminder rules."""
    if not recurrence:
        return None

    try:
        dt = datetime.fromisoformat(current_remind_at)
    except Exception:
        try:
            dt = datetime.strptime(current_remind_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    rec = recurrence.upper().strip()
    if rec in ("DAILY", "EVERY DAY", "EVERYDAY"):
        next_dt = dt + timedelta(days=1)
    elif rec in ("WEEKLY", "EVERY WEEK"):
        next_dt = dt + timedelta(weeks=1)
    elif rec in ("MONTHLY", "EVERY MONTH"):
        # Approximation: +30 days or same day next month
        year = dt.year + (1 if dt.month == 12 else 0)
        month = 1 if dt.month == 12 else dt.month + 1
        day = min(dt.day, 28)
        next_dt = dt.replace(year=year, month=month, day=day)
    elif rec in ("WEEKDAYS", "MON-FRI", "EVERY WEEKDAY"):
        next_dt = dt + timedelta(days=1)
        while next_dt.weekday() >= 5:  # 5=Sat, 6=Sun
            next_dt += timedelta(days=1)
    else:
        # Default fallback
        next_dt = dt + timedelta(days=1)

    return next_dt.strftime("%Y-%m-%d %H:%M:%S")


class ReminderService:
    """Domain service managing reminder creation, recurrence, and lifecycle."""

    def __init__(self, reminder_repo: Optional[ReminderRepository] = None):
        self.repo = reminder_repo or ReminderRepository()

    def create_reminder(
        self,
        reminder_text: str,
        remind_at: str,
        user_id: int = 0,
        task_id: Optional[int] = None,
        recurrence: Optional[str] = None,
        timezone: str = DEFAULT_TIMEZONE
    ) -> ReminderRecord:
        """Create and persist a new reminder."""
        clean_text = reminder_text.strip()
        if not clean_text:
            raise DomainValidationError("Reminder text cannot be empty.")
        if len(clean_text) > 500:
            raise DomainValidationError("Reminder text cannot exceed 500 characters.")

        # Normalize remind_at string
        clean_remind_at = remind_at.strip()
        if not clean_remind_at:
            raise DomainValidationError("Reminder scheduled time 'remind_at' is required.")

        reminder_id = self.repo.create(
            reminder_text=clean_text,
            remind_at=clean_remind_at,
            user_id=user_id,
            task_id=task_id,
            recurrence=recurrence,
            timezone=timezone
        )
        rem = self.repo.get_by_id(reminder_id)
        if not rem:
            raise NotFoundError(f"Failed to load created reminder #{reminder_id}")

        logger.info(f"Created reminder #{rem.id}: '{rem.reminder_text}' for {rem.remind_at} ({rem.recurrence or 'once'})")
        return rem

    def get_reminder(self, reminder_id: int) -> ReminderRecord:
        """Fetch reminder by ID."""
        rem = self.repo.get_by_id(reminder_id)
        if not rem:
            raise NotFoundError(f"Reminder #{reminder_id} not found.")
        return rem

    def list_upcoming(self, user_id: int = 0, limit: int = 20) -> List[ReminderRecord]:
        """List upcoming pending reminders."""
        return self.repo.list_upcoming(user_id=user_id, limit=limit)

    def cancel_reminder(self, reminder_id: int) -> ReminderRecord:
        """Cancel reminder."""
        rem = self.get_reminder(reminder_id)
        self.repo.cancel(reminder_id)
        logger.info(f"Cancelled reminder #{reminder_id}.")
        return self.get_reminder(reminder_id)
