"""Reminder domain service and scheduler helper calculations for Asia/Kolkata timezone."""

import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import zoneinfo

from app.core.exceptions import DomainValidationError, NotFoundError
from app.core.logging import get_logger
from app.database.repositories.reminder import ReminderRecord, ReminderRepository

logger = get_logger("services.reminder")

DEFAULT_TIMEZONE = "Asia/Kolkata"


def _tz(tz_str: str = DEFAULT_TIMEZONE) -> zoneinfo.ZoneInfo:
    """Safely get a ZoneInfo object, falling back to Asia/Kolkata."""
    try:
        return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        return zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


def parse_and_normalize_remind_at(
    remind_at_raw: str,
    timezone_str: str = DEFAULT_TIMEZONE
) -> Tuple[str, Optional[str]]:
    """
    Parse any human-readable time/date string into:
        (canonical_iso_datetime_str, recurrence_str_or_None)

    canonical_iso_datetime_str: "YYYY-MM-DD HH:MM:SS" in the given timezone
    recurrence_str_or_None: "DAILY", "WEEKLY", etc. or None for one-time

    Handles:
    - "HH:MM"               e.g. "10:45"
    - "HH:MM:SS"            e.g. "10:45:00"
    - "HH:MM AM/PM"         e.g. "10:45 PM", "8:00 AM"
    - "HH AM/PM"            e.g. "8 AM", "10 PM"
    - "in X minutes/hours"  e.g. "in 30 minutes", "in 2 hours"
    - "tomorrow at HH:MM"   e.g. "tomorrow at 8 AM"
    - Full ISO datetime      e.g. "2026-09-27 10:45:00"
    - "every day at HH:MM"  → DAILY recurrence
    - "daily at HH:MM"      → DAILY recurrence

    Past-time rule: if the computed time is in the past, adds 1 day.
    """
    tz = _tz(timezone_str)
    now = datetime.now(tz)
    raw = remind_at_raw.strip()
    recurrence: Optional[str] = None

    # ── 0. Detect DAILY recurrence phrases ──────────────────────────────────
    daily_patterns = [
        r"(?:every\s+day|everyday|daily|each\s+day|every\s+morning|every\s+evening|every\s+night)",
    ]
    for pat in daily_patterns:
        if re.search(pat, raw, re.IGNORECASE):
            recurrence = "DAILY"
            # Strip the recurrence prefix so we can extract the time part
            raw = re.sub(pat, "", raw, flags=re.IGNORECASE).strip()
            raw = re.sub(r"^(?:at|@)\s*", "", raw, flags=re.IGNORECASE).strip()
            break

    # ── 1. Full ISO datetime (already canonical) ─────────────────────────────
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            dt = datetime.strptime(raw, fmt)
            dt_aware = dt.replace(tzinfo=tz)
            return dt_aware.strftime("%Y-%m-%d %H:%M:%S"), recurrence
        except ValueError:
            pass

    # ── 2. Relative: "in X minutes" / "in X hours" ──────────────────────────
    rel_match = re.match(r"in\s+(\d+)\s+(minute|minutes|min|hour|hours|hr|hrs)", raw, re.IGNORECASE)
    if rel_match:
        qty = int(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if "hour" in unit or "hr" in unit:
            dt = now + timedelta(hours=qty)
        else:
            dt = now + timedelta(minutes=qty)
        return dt.strftime("%Y-%m-%d %H:%M:%S"), recurrence

    # ── 3. "tomorrow at HH:MM [AM/PM]" ──────────────────────────────────────
    tomorrow_match = re.match(
        r"tomorrow\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        raw, re.IGNORECASE
    )
    if tomorrow_match:
        hour = int(tomorrow_match.group(1))
        minute = int(tomorrow_match.group(2) or 0)
        ampm = (tomorrow_match.group(3) or "").lower()
        hour = _apply_ampm(hour, ampm)
        tomorrow = now + timedelta(days=1)
        dt = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return dt.strftime("%Y-%m-%d %H:%M:%S"), recurrence

    # ── 4. "HH:MM AM/PM", "HH AM/PM", "HH:MM", "HH:MM:SS" ─────────────────
    # Remove leading "at " if present
    time_str = re.sub(r"^at\s+", "", raw, flags=re.IGNORECASE).strip()

    time_match = re.match(
        r"^(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(am|pm)?$",
        time_str, re.IGNORECASE
    )
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        second = int(time_match.group(3) or 0)
        ampm = (time_match.group(4) or "").lower()
        hour = _apply_ampm(hour, ampm)
        dt = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        # Past-time rollover: schedule for tomorrow if time has passed (>30s buffer)
        if dt <= now + timedelta(seconds=30):
            dt = dt + timedelta(days=1)
        return dt.strftime("%Y-%m-%d %H:%M:%S"), recurrence

    # ── 5. Fallback: return as-is if already valid YYYY-MM-DD ... ────────────
    logger.warning(f"Could not parse remind_at='{remind_at_raw}'; using raw value.")
    return raw, recurrence


def _apply_ampm(hour: int, ampm: str) -> int:
    """Convert 12h hour + AM/PM to 24h hour."""
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return hour


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
        year = dt.year + (1 if dt.month == 12 else 0)
        month = 1 if dt.month == 12 else dt.month + 1
        day = min(dt.day, 28)
        next_dt = dt.replace(year=year, month=month, day=day)
    elif rec in ("WEEKDAYS", "MON-FRI", "EVERY WEEKDAY"):
        next_dt = dt + timedelta(days=1)
        while next_dt.weekday() >= 5:  # 5=Sat, 6=Sun
            next_dt += timedelta(days=1)
    else:
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
        """Create and persist a new reminder, normalizing the remind_at timestamp."""
        clean_text = reminder_text.strip()
        if not clean_text:
            raise DomainValidationError("Reminder text cannot be empty.")
        if len(clean_text) > 500:
            raise DomainValidationError("Reminder text cannot exceed 500 characters.")

        clean_remind_at = (remind_at or "").strip()
        if not clean_remind_at:
            raise DomainValidationError("Reminder scheduled time 'remind_at' is required.")

        # Normalize the time string into a full ISO datetime
        normalized_remind_at, detected_recurrence = parse_and_normalize_remind_at(clean_remind_at, timezone)

        # Merge detected recurrence (e.g. from "every day at 8 AM") with explicit recurrence arg
        final_recurrence = recurrence or detected_recurrence

        reminder_id = self.repo.create(
            reminder_text=clean_text,
            remind_at=normalized_remind_at,
            user_id=user_id,
            task_id=task_id,
            recurrence=final_recurrence,
            timezone=timezone
        )
        rem = self.repo.get_by_id(reminder_id)
        if not rem:
            raise NotFoundError(f"Failed to load created reminder #{reminder_id}")

        logger.info(
            f"Created reminder #{rem.id}: '{rem.reminder_text}' "
            f"for {rem.remind_at} ({rem.recurrence or 'once'})"
        )
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
