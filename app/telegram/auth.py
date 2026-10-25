"""Centralized Telegram authorization guard.

Enforces that only the configured settings.telegram_allowed_user_id can interact
with the bot, view personal data, execute database transactions, or trigger AI processing.
"""

from functools import wraps
from typing import Any, Callable, Coroutine, Optional

try:
    from telegram import Update
    from telegram.ext import ContextTypes
except ImportError:
    Update = Any  # type: ignore

    class _MockContextTypes:
        DEFAULT_TYPE = Any

    ContextTypes = _MockContextTypes  # type: ignore

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("telegram.auth")


def is_user_authorized(user_id: Optional[int]) -> bool:
    """
    Check if a numeric Telegram user ID is authorized.
    
    Invariants:
    1. If settings.telegram_allowed_user_id is None or 0, fail closed (returns False).
    2. Only strictly matching numeric IDs are permitted.
    """
    allowed_id = settings.telegram_allowed_user_id
    if not allowed_id or not isinstance(allowed_id, int) or allowed_id <= 0:
        logger.warning("TELEGRAM_ALLOWED_USER_ID is not configured or invalid. Failing closed.")
        return False

    if user_id is None or not isinstance(user_id, int):
        return False

    return user_id == allowed_id


def authorized_only(
    handler_func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    """
    Decorator for Telegram handler functions (commands, messages, photos, callbacks).
    
    Rejects unauthorized updates before any handler execution, ensuring zero AI invocations,
    zero database reads/mutations, and zero data leakage.
    """
    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        effective_user = update.effective_user
        user_id = effective_user.id if effective_user else None

        if not is_user_authorized(user_id):
            logger.warning(
                f"Unauthorized update attempt blocked from user ID: {user_id} "
                f"(handler: {handler_func.__name__})"
            )
            # For callback queries, answer with alert without revealing data
            if update.callback_query:
                try:
                    await update.callback_query.answer("⛔ Unauthorized access.", show_alert=True)
                except Exception:
                    pass
                return

            # For messages, return non-descriptive error
            if update.effective_message:
                try:
                    await update.effective_message.reply_text("⛔ Access denied.")
                except Exception:
                    pass
            return

        return await handler_func(update, context)

    return wrapper
