"""Standalone, persistent reminder background scheduler for Termux deployment.

Key Invariants:
1. Zero Gemini/LLM dependency in scheduler loop.
2. Transaction-safe state transitions (PENDING -> CLAIMED -> SENT).
3. Deduplication guarantee: A reminder cannot be double-notified on restart or poll overlap.
4. Auto-reconnect and safe retry on Telegram/network failure (CLAIMED -> PENDING).
5. Survives process restart and phone reboot.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
import zoneinfo

try:
    from telegram import Bot
except ImportError:
    Bot = Any  # type: ignore

from app.core.config import settings
from app.core.logging import get_logger
from app.database.repositories.reminder import ReminderRecord, ReminderRepository
from app.services.reminder.service import calculate_next_recurrence

logger = get_logger("services.reminder.scheduler")



class ReminderScheduler:
    """Lightweight background reminder scheduler running in polling loop."""

    def __init__(
        self,
        reminder_repo: Optional[ReminderRepository] = None,
        bot: Optional[Bot] = None,
        poll_interval_seconds: int = 15,
        target_chat_id: Optional[int] = None,
    ):
        self.repo = reminder_repo or ReminderRepository()
        self.bot = bot
        self.poll_interval = poll_interval_seconds
        self.target_chat_id = target_chat_id or settings.telegram_allowed_user_id
        self._running = False

    def get_current_kolkata_time(self) -> str:
        """Get current ISO time formatted in Asia/Kolkata."""
        try:
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            now = datetime.now(tz)
        except Exception:
            now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    async def poll_and_dispatch(self) -> int:
        """
        Execute one poll cycle:
        1. Atomic CLAIM of due reminders (status=PENDING -> CLAIMED).
        2. Deliver Telegram notification.
        3. On success: mark SENT or calculate next occurrence if recurring.
        4. On failure: release back to PENDING for subsequent retry.
        """
        now_str = self.get_current_kolkata_time()
        claimed_reminders = self.repo.claim_due_reminders(now_str, limit=10)

        if not claimed_reminders:
            return 0

        logger.info(f"Claimed {len(claimed_reminders)} due reminders for delivery at {now_str}")
        sent_count = 0

        for rem in claimed_reminders:
            success = await self._dispatch_single(rem)
            if success:
                sent_count += 1

        return sent_count

    async def _dispatch_single(self, rem: ReminderRecord) -> bool:
        """Deliver single reminder notification with safe fallback and recovery."""
        chat_id = rem.user_id if rem.user_id != 0 else self.target_chat_id
        message_text = f"🔔 *Reminder Alert!*\n\n{rem.reminder_text}"
        if rem.recurrence:
            message_text += f"\n\n🔁 _Recurring: {rem.recurrence}_"

        try:
            if self.bot and chat_id:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    parse_mode="Markdown"
                )
                logger.info(f"Delivered reminder #{rem.id} to chat {chat_id}")
            else:
                logger.info(f"[NO BOT/DRY RUN] Reminder #{rem.id}: {rem.reminder_text}")

            # Mark sent or schedule next recurrence
            now_str = self.get_current_kolkata_time()
            next_trigger = calculate_next_recurrence(rem.remind_at, rem.recurrence, rem.timezone)
            self.repo.mark_sent(rem.id, triggered_at=now_str, next_trigger_at=next_trigger)
            return True

        except Exception as e:
            logger.error(f"Failed to deliver reminder #{rem.id} via Telegram: {e}. Releasing claim.", exc_info=True)
            self.repo.release_claimed_to_pending(rem.id)
            return False

    async def start_loop(self) -> None:
        """Run persistent async polling loop."""
        self._running = True
        logger.info(f"Starting ReminderScheduler loop (interval: {self.poll_interval}s)...")
        while self._running:
            try:
                await self.poll_and_dispatch()
            except Exception as e:
                logger.error(f"Error in ReminderScheduler poll loop: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop polling loop."""
        self._running = False
        logger.info("Stopped ReminderScheduler loop.")
