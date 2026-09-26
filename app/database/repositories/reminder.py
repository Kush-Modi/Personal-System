"""Reminder repository for persistent reminder management, state transitions, and scheduling."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.database.repositories.base import BaseRepository


@dataclass
class ReminderRecord:
    id: int
    task_id: Optional[int]
    user_id: int
    reminder_text: str
    remind_at: str
    recurrence: Optional[str]  # DAILY, WEEKLY, MONTHLY, WEEKDAYS, etc.
    timezone: str
    status: str  # PENDING, CLAIMED, SENT, CANCELLED
    created_at: str
    updated_at: str
    last_triggered_at: Optional[str]
    next_trigger_at: Optional[str]


class ReminderRepository(BaseRepository):
    """Repository handling reminder CRUD and atomic scheduler state transitions."""

    def create(
        self,
        reminder_text: str,
        remind_at: str,
        user_id: int = 0,
        task_id: Optional[int] = None,
        recurrence: Optional[str] = None,
        timezone: str = "Asia/Kolkata",
    ) -> int:
        """Create a new reminder."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reminders (
                    user_id, task_id, reminder_text, remind_at, recurrence, timezone, status, next_trigger_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?);
                """,
                (user_id, task_id, reminder_text, remind_at, recurrence, timezone, remind_at)
            )
            return cursor.lastrowid

    def get_by_id(self, reminder_id: int) -> Optional[ReminderRecord]:
        """Fetch reminder by ID."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, task_id, user_id, reminder_text, remind_at, recurrence, timezone,
                       status, created_at, updated_at, last_triggered_at, next_trigger_at
                FROM reminders WHERE id = ?;
                """,
                (reminder_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ReminderRecord(
                id=row["id"],
                task_id=row["task_id"],
                user_id=row["user_id"],
                reminder_text=row["reminder_text"],
                remind_at=row["remind_at"],
                recurrence=row["recurrence"],
                timezone=row["timezone"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_triggered_at=row["last_triggered_at"],
                next_trigger_at=row["next_trigger_at"]
            )

    def claim_due_reminders(self, current_iso_time: str, limit: int = 10) -> List[ReminderRecord]:
        """
        Atomically find and claim due reminders to prevent duplicate notifications across concurrent polling.
        Transitions state: PENDING -> CLAIMED in a single transaction.
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            # Select due IDs
            cursor.execute(
                """
                SELECT id
                FROM reminders
                WHERE status = 'PENDING'
                  AND datetime(next_trigger_at) <= datetime(?)
                ORDER BY datetime(next_trigger_at) ASC
                LIMIT ?;
                """,
                (current_iso_time, limit)
            )
            ids = [row[0] for row in cursor.fetchall()]
            if not ids:
                return []

            placeholders = ",".join("?" * len(ids))
            cursor.execute(
                f"""
                UPDATE reminders
                SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders});
                """,
                ids
            )

            cursor.execute(
                f"""
                SELECT id, task_id, user_id, reminder_text, remind_at, recurrence, timezone,
                       status, created_at, updated_at, last_triggered_at, next_trigger_at
                FROM reminders WHERE id IN ({placeholders});
                """,
                ids
            )
            return [
                ReminderRecord(
                    id=row["id"],
                    task_id=row["task_id"],
                    user_id=row["user_id"],
                    reminder_text=row["reminder_text"],
                    remind_at=row["remind_at"],
                    recurrence=row["recurrence"],
                    timezone=row["timezone"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_triggered_at=row["last_triggered_at"],
                    next_trigger_at=row["next_trigger_at"]
                )
                for row in cursor.fetchall()
            ]

    def mark_sent(
        self,
        reminder_id: int,
        triggered_at: str,
        next_trigger_at: Optional[str] = None
    ) -> bool:
        """
        Mark reminder as SENT (or back to PENDING with next_trigger_at for recurring reminders).
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            if next_trigger_at:
                cursor.execute(
                    """
                    UPDATE reminders
                    SET status = 'PENDING',
                        last_triggered_at = ?,
                        next_trigger_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (triggered_at, next_trigger_at, reminder_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE reminders
                    SET status = 'SENT',
                        last_triggered_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (triggered_at, reminder_id)
                )
            return cursor.rowcount > 0

    def release_claimed_to_pending(self, reminder_id: int) -> bool:
        """Release a CLAIMED reminder back to PENDING if network transmission fails."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE reminders
                SET status = 'PENDING', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'CLAIMED';
                """,
                (reminder_id,)
            )
            return cursor.rowcount > 0

    def list_upcoming(self, user_id: int = 0, limit: int = 20) -> List[ReminderRecord]:
        """List active pending reminders ordered by next trigger time."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, task_id, user_id, reminder_text, remind_at, recurrence, timezone,
                       status, created_at, updated_at, last_triggered_at, next_trigger_at
                FROM reminders
                WHERE status = 'PENDING'
                ORDER BY datetime(next_trigger_at) ASC
                LIMIT ?;
                """,
                (limit,)
            )
            return [
                ReminderRecord(
                    id=row["id"],
                    task_id=row["task_id"],
                    user_id=row["user_id"],
                    reminder_text=row["reminder_text"],
                    remind_at=row["remind_at"],
                    recurrence=row["recurrence"],
                    timezone=row["timezone"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_triggered_at=row["last_triggered_at"],
                    next_trigger_at=row["next_trigger_at"]
                )
                for row in cursor.fetchall()
            ]

    def cancel(self, reminder_id: int) -> bool:
        """Cancel a reminder."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE reminders
                SET status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (reminder_id,)
            )
            return cursor.rowcount > 0
